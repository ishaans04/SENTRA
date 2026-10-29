"""Gate 1: PS-001 fires on live gateway calls."""

from __future__ import annotations

from pathlib import Path

from sentra.scenario import Session


def _call_id(session: Session, run_id: str, tool: str) -> str:
    for event in session.ledger.events():
        if (
            event.kind == "gateway.call"
            and event.run_id == run_id
            and event.payload["tool"] == tool
        ):
            return event.event_id
    raise AssertionError(f"no {tool} call by {run_id}")


async def test_ps001_fires_on_live_gateway_calls(fixtures_dir: Path) -> None:
    session = Session("s-gate1", fixtures_dir)
    await session.run_to(5)

    findings = [e for e in session.ledger.events() if e.kind == "finding.raised"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.payload["rule_id"] == "PS-001"
    assert finding.cites == [
        _call_id(session, "S-1", "crm.read_customer_records"),
        _call_id(session, "S-1", "scratchpad.write"),
        _call_id(session, "R-1", "scratchpad.read"),
        _call_id(session, "R-1", "webhook.send_report"),
    ]

    proposed = [e for e in session.ledger.events() if e.kind == "containment.proposed"]
    assert len(proposed) == 1
    assert proposed[0].cites == [finding.event_id]
    assert proposed[0].payload["recommended_capability_id"] == "deny-reporting-scratchpad-read"


async def test_finding_only_after_the_withdrawal(fixtures_dir: Path) -> None:
    session = Session("s-gate1b", fixtures_dir)
    await session.run_to(4)
    assert not [e for e in session.ledger.events() if e.kind == "finding.raised"]


async def test_human_edit_is_a_new_version_by_the_teammate(fixtures_dir: Path) -> None:
    session = Session("s-gate1c", fixtures_dir)
    await session.run_to(4)
    draft = session.world.items["draft-1"]
    assert (draft.version, draft.writer) == (2, "teammate")
    edits = [e for e in session.ledger.events() if e.kind == "item.version_changed"]
    assert edits[-1].payload == {"item": "draft-1", "version": 2, "writer": "teammate"}


async def test_scripted_agent_survives_a_rejection(fixtures_dir: Path) -> None:
    session = Session("s-gate1d", fixtures_dir)
    await session.run_to(3)
    session.gateway.state.runs["R-1"].status = "cancelled"
    result = await session.agent("R-1").call("report_store.read_summaries", {})
    assert result.ok is False
    assert result.error == "run_cancelled"
