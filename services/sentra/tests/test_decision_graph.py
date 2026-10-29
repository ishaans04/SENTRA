"""The decision graph is a fold over ledger events, with the earned-fact rule."""

from __future__ import annotations

import pytest

from sentra.clock import LogicalClock
from sentra.conditions.predicates import ReadsOnlyFrom
from sentra.decisions.graph import DecisionGraph
from sentra.decisions.models import Basis, Condition, Decision
from sentra.ledger import SessionLedger


def _seed(ledger: SessionLedger, graph: DecisionGraph) -> None:
    condition = Condition(
        id="C-1",
        predicate=ReadsOnlyFrom(
            actor="reporting-agent", resources=["report_store/approved_summaries"]
        ),
        plain="this agent receives only sanitized summaries",
    )
    decision = Decision(
        id="D-1",
        statement="Reporting may proceed",
        subject="Reporting",
        actor="reporting-agent",
        dictated_text="Approve reporting...",
        bases=[Basis(id="B-1", conditions=["C-1"])],
    )
    for event in (
        ledger.append(
            "decision.proposed",
            "sentra",
            decision_id="D-1",
            payload={"decision": decision.model_dump(), "conditions": [condition.model_dump()]},
        ),
        ledger.append("decision.confirmed", "operator", decision_id="D-1", epoch=1),
        ledger.append(
            "run.started",
            "gateway",
            actor="reporting-agent",
            run_id="R-1",
            decision_id="D-1",
            epoch=1,
        ),
        ledger.append(
            "decision.suspended", "sentra", decision_id="D-1", epoch=2, payload={"new_epoch": 2}
        ),
    ):
        graph.apply(event)


def test_states_follow_the_events() -> None:
    ledger = SessionLedger("s", LogicalClock())
    graph = DecisionGraph()
    _seed(ledger, graph)
    decision = graph.decisions["D-1"]
    assert (decision.status, decision.epoch) == ("suspended", 2)
    assert graph.graph.has_edge("D-1", "C-1", key="DEPENDS_ON")
    assert graph.graph.has_edge("D-1", "R-1", key="AUTHORIZES")


def test_graph_rebuilt_from_ledger_is_identical() -> None:
    ledger = SessionLedger("s", LogicalClock())
    original = DecisionGraph()
    _seed(ledger, original)
    rebuilt = DecisionGraph.replay(SessionLedger.parse_jsonl(ledger.to_jsonl()))
    assert rebuilt.snapshot() == original.snapshot()


def test_checked_requires_verified_by() -> None:
    ledger = SessionLedger("s", LogicalClock())
    graph = DecisionGraph()
    unlinked = ledger.append(
        "evidence.recorded",
        "verification",
        payload={"id": "E-1", "kind": "checked", "source": "check:route_closed"},
    )
    with pytest.raises(ValueError, match="VERIFIED_BY"):
        graph.apply(unlinked)
    linked = ledger.append(
        "evidence.recorded",
        "verification",
        payload={
            "id": "E-2",
            "kind": "checked",
            "source": "check:route_closed",
            "verifies": "plan-1",
        },
    )
    graph.apply(linked)
    assert graph.graph.has_edge("plan-1", "E-2", key="VERIFIED_BY")
    assert graph.evidence["E-2"].kind == "checked"


def test_stated_evidence_needs_no_link() -> None:
    ledger = SessionLedger("s", LogicalClock())
    graph = DecisionGraph()
    graph.apply(
        ledger.append(
            "evidence.recorded",
            "operator",
            payload={"id": "E-1", "kind": "stated", "source": "operator"},
        )
    )
    assert graph.evidence["E-1"].kind == "stated"
