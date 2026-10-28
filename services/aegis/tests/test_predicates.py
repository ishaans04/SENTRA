"""The three typed condition predicates: HOLDS, FAILS and UNKNOWN for each."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.clock import LogicalClock
from aegis.conditions.predicates import (
    ConditionContext,
    ManifestUnchanged,
    NoUndeclaredPath,
    ReadsOnlyFrom,
)
from aegis.hive_bridge import HiveBridge
from aegis.ledger import LedgerEvent, SessionLedger

APPROVED = "report_store/approved_summaries"


class World:
    def __init__(self, fixtures_dir: Path) -> None:
        self.ledger = SessionLedger("s-pred", LogicalClock())
        self.bridge = HiveBridge(fixtures_dir / "manifest.yaml")

    def call(
        self,
        actor: str,
        effect: str,
        resource: str,
        *,
        epoch: int = 1,
        decision: str = "D-1",
        observe: bool = True,
    ) -> LedgerEvent:
        event = self.ledger.append(
            "gateway.call",
            "gateway",
            actor=actor,
            run_id="R-x",
            decision_id=decision,
            epoch=epoch,
            payload={"tool": "t", "effect": effect, "resource": resource, "outcome": "executed"},
        )
        if observe:
            self.bridge.observe(event)
        return event

    def ctx(self, epoch: int = 1) -> ConditionContext:
        return ConditionContext(
            events=self.ledger.events(), bridge=self.bridge, decision_id="D-1", epoch=epoch
        )

    def route(self) -> None:
        self.call("support-agent", "read", "crm", decision="D-0")
        self.call("support-agent", "write", "scratchpad", decision="D-0")
        self.call("reporting-agent", "read", "scratchpad")
        self.call("reporting-agent", "send", "webhook")


@pytest.fixture
def world(fixtures_dir: Path) -> World:
    return World(fixtures_dir)


class TestReadsOnlyFrom:
    predicate = ReadsOnlyFrom(actor="reporting-agent", resources=[APPROVED])

    def test_holds(self, world: World) -> None:
        world.call("reporting-agent", "read", APPROVED)
        assert self.predicate.evaluate(world.ctx()).result == "HOLDS"

    def test_fails_with_the_offending_read_as_witness(self, world: World) -> None:
        world.call("reporting-agent", "read", APPROVED)
        bad = world.call("reporting-agent", "read", "scratchpad")
        outcome = self.predicate.evaluate(world.ctx())
        assert outcome.result == "FAILS"
        assert outcome.witnesses == [bad.event_id]

    def test_unknown_when_a_read_never_reached_hive(self, world: World) -> None:
        world.call("reporting-agent", "read", APPROVED, observe=False)
        assert self.predicate.evaluate(world.ctx()).result == "UNKNOWN"

    def test_reads_before_current_epoch_are_ignored(self, world: World) -> None:
        world.call("reporting-agent", "read", "scratchpad", epoch=1)
        world.call("reporting-agent", "read", APPROVED, epoch=2)
        assert self.predicate.evaluate(world.ctx(epoch=2)).result == "HOLDS"

    def test_other_decisions_are_ignored(self, world: World) -> None:
        world.call("reporting-agent", "read", "scratchpad", decision="D-9")
        assert self.predicate.evaluate(world.ctx()).result == "HOLDS"


class TestNoUndeclaredPath:
    predicate = NoUndeclaredPath(source="crm", sink="webhook")

    def test_holds(self, world: World) -> None:
        world.call("support-agent", "read", "crm", decision="D-0")
        world.call("reporting-agent", "send", "webhook")
        assert self.predicate.evaluate(world.ctx()).result == "HOLDS"

    def test_fails_on_the_composed_route(self, world: World) -> None:
        world.route()
        outcome = self.predicate.evaluate(world.ctx())
        assert outcome.result == "FAILS"
        assert len(outcome.witnesses) == 4

    def test_unknown_before_the_source_is_observed(self, world: World) -> None:
        assert self.predicate.evaluate(world.ctx()).result == "UNKNOWN"


class TestManifestUnchanged:
    predicate = ManifestUnchanged(actor="reporting-agent")

    def test_holds(self, world: World) -> None:
        world.call("reporting-agent", "read", APPROVED)
        assert self.predicate.evaluate(world.ctx()).result == "HOLDS"

    def test_fails_on_an_undeclared_resource(self, world: World) -> None:
        bad = world.call("reporting-agent", "read", "scratchpad")
        outcome = self.predicate.evaluate(world.ctx())
        assert outcome.result == "FAILS"
        assert outcome.witnesses == [bad.event_id]

    def test_unknown_for_an_actor_not_in_the_manifest(self, world: World) -> None:
        outcome = ManifestUnchanged(actor="ghost-agent").evaluate(world.ctx())
        assert outcome.result == "UNKNOWN"


def test_predicates_describe_themselves() -> None:
    predicate = ReadsOnlyFrom(actor="reporting-agent", resources=[APPROVED])
    assert predicate.describe() == "reporting-agent only reads from report_store/approved_summaries"
    assert NoUndeclaredPath(source="crm", sink="webhook").describe() == (
        "no undeclared route from crm to webhook"
    )
