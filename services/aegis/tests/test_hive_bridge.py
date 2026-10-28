"""The session ledger and the bridge that feeds gateway calls to HIVE."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.clock import LogicalClock
from aegis.hive_bridge import HiveBridge
from aegis.ledger import LedgerEvent, SessionLedger


@pytest.fixture
def ledger() -> SessionLedger:
    return SessionLedger("s-test", LogicalClock())


def _call(
    ledger: SessionLedger, actor: str, tool: str, effect: str, resource: str, **extra: object
) -> LedgerEvent:
    payload: dict[str, object] = {
        "tool": tool,
        "effect": effect,
        "resource": resource,
        "outcome": "executed",
    }
    payload.update(extra)
    return ledger.append("gateway.call", "gateway", actor=actor, run_id="R-x", payload=payload)


def _route(ledger: SessionLedger, bridge: HiveBridge) -> list[list[str]]:
    hops = [
        ("support-agent", "crm.read_customer_records", "read", "crm"),
        ("support-agent", "scratchpad.write", "write", "scratchpad"),
        ("reporting-agent", "scratchpad.read", "read", "scratchpad"),
        ("reporting-agent", "webhook.send_report", "send", "webhook"),
    ]
    return [[f.id for f in bridge.observe(_call(ledger, *hop))] for hop in hops]


class TestSessionLedger:
    def test_sequence_and_clock_are_deterministic(self, ledger: SessionLedger) -> None:
        first = ledger.append("session.seeded", "scenario")
        second = ledger.append("session.seeded", "scenario")
        assert (first.seq, first.event_id, first.at) == (1, "ev-000001", "2026-10-28T10:00:01Z")
        assert second.seq == 2

    def test_unknown_kind_is_refused(self, ledger: SessionLedger) -> None:
        with pytest.raises(ValueError, match="Unknown event kind"):
            ledger.append("made.up", "scenario")

    def test_jsonl_round_trip(self, ledger: SessionLedger) -> None:
        ledger.append("session.seeded", "scenario", payload={"x": 1})
        assert SessionLedger.parse_jsonl(ledger.to_jsonl()) == ledger.events()

    async def test_subscribers_receive_new_events(self, ledger: SessionLedger) -> None:
        queue = ledger.subscribe()
        event = ledger.append("session.seeded", "scenario")
        assert queue.get_nowait() == event


class TestHiveBridge:
    def test_route_raises_ps001_once(self, ledger: SessionLedger, fixtures_dir: Path) -> None:
        bridge = HiveBridge(fixtures_dir / "manifest.yaml")
        new_per_call = _route(ledger, bridge)
        assert [len(ids) for ids in new_per_call] == [0, 0, 0, 1]
        again = _call(ledger, "reporting-agent", "webhook.send_report", "send", "webhook")
        assert bridge.observe(again) == []
        assert [f.rule_id for f in bridge.open_findings()] == ["PS-001"]

    def test_grant_is_not_a_hive_hop(self, ledger: SessionLedger, fixtures_dir: Path) -> None:
        bridge = HiveBridge(fixtures_dir / "manifest.yaml")
        grant = _call(ledger, "support-agent", "scratchpad.grant_access", "grant", "scratchpad")
        assert bridge.observe(grant) == []
        assert bridge.observation_count() == 0

    def test_rejected_call_is_not_a_hive_hop(
        self, ledger: SessionLedger, fixtures_dir: Path
    ) -> None:
        bridge = HiveBridge(fixtures_dir / "manifest.yaml")
        rejected = _call(
            ledger, "reporting-agent", "webhook.send_report", "send", "webhook", outcome="rejected"
        )
        bridge.observe(rejected)
        assert bridge.observation_count() == 0

    def test_observation_is_redacted(self, ledger: SessionLedger, fixtures_dir: Path) -> None:
        bridge = HiveBridge(fixtures_dir / "manifest.yaml")
        call = _call(
            ledger, "support-agent", "scratchpad.write", "write", "scratchpad", content="secret"
        )
        bridge.observe(call)
        stored = bridge.observations()[0]
        assert stored.context["content"] == "[redacted at ingest]"

    def test_block_closes_the_route(self, ledger: SessionLedger, fixtures_dir: Path) -> None:
        bridge = HiveBridge(fixtures_dir / "manifest.yaml")
        finding_id = _route(ledger, bridge)[-1][0]
        plan = bridge.plan(finding_id)
        assert plan.recommended_capability_id == "deny-reporting-scratchpad-read"
        bridge.apply_block(
            "deny-reporting-scratchpad-read",
            ledger.append(
                "containment.applied",
                "recovery",
                payload={"capability_id": plan.recommended_capability_id},
            ),
        )
        assert bridge.rerun_rules() == []
