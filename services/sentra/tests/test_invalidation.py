"""Forward invalidation: a finding withdraws the approval its runs stand on."""

from __future__ import annotations

from pathlib import Path

from sentra.conditions.predicates import ManifestUnchanged, ReadsOnlyFrom
from sentra.decisions.models import ConditionProposal, DecisionProposal
from sentra.scenario import Session

APPROVED = "report_store/approved_summaries"


def _reporting(*conditions: ConditionProposal) -> DecisionProposal:
    return DecisionProposal(
        statement="Reporting may proceed",
        subject="Reporting",
        actor="reporting-agent",
        conditions=list(conditions),
    )


C1 = ConditionProposal(
    predicate=ReadsOnlyFrom(actor="reporting-agent", resources=[APPROVED]),
    plain="this agent receives only sanitized summaries",
)


def _kinds(session: Session, kind: str) -> list:
    return [e for e in session.ledger.events() if e.kind == kind]


async def _approved(fixtures_dir: Path, proposal: DecisionProposal) -> Session:
    """A session whose D-1 is *proposal*, confirmed, with the storyline past beat 1."""
    session = Session("s-inv", fixtures_dir)
    decision = session.decisions.propose(proposal, "Approve reporting...")
    session.decisions.confirm(decision.id)
    session.position = 2
    return session


async def test_fail_suspends_and_bumps_epoch(fixtures_dir: Path) -> None:
    session = await _approved(fixtures_dir, _reporting(C1))
    await session.run_to(5)
    d1 = session.decisions.get("D-1")
    assert (d1.status, d1.epoch) == ("suspended", 2)
    evaluated = [
        e for e in _kinds(session, "condition.evaluated") if e.payload["result"] == "FAILS"
    ]
    assert evaluated and evaluated[0].payload["condition_id"] == "C-1"
    assert session.gateway.outbox.get("A-1").status == "held"
    assert session.gateway.state.runs["R-1"].status == "stale"
    assert session.decisions.graph.runs["R-1"] == "stale"
    assert session.decisions.graph.actions["A-1"] == "held"


async def test_one_alert_with_the_prd_wording(fixtures_dir: Path) -> None:
    session = await _approved(fixtures_dir, _reporting(C1))
    await session.run_to(5)
    alerts = _kinds(session, "alert.raised")
    assert len(alerts) == 1
    assert alerts[0].payload["text"] == (
        "Reporting was approved on the condition that this agent receives only sanitized "
        "summaries. It has now read an undeclared shared scratchpad. An external report is "
        "queued. This run needs review."
    )


async def test_another_basis_keeps_decision_active(fixtures_dir: Path) -> None:
    session = Session("s-inv2", fixtures_dir)
    support_unchanged = ConditionProposal(
        predicate=ManifestUnchanged(actor="support-agent"), plain="support is unchanged"
    )
    decision = session.decisions.propose(_reporting(C1), "", extra_bases=[[support_unchanged]])
    session.decisions.confirm(decision.id)
    session.decisions.start_run("R-1", decision.id)
    session.gateway.world.grants.add(("reporting-agent", "scratchpad"))
    await session.agent("R-1").call("scratchpad.read", {})
    decision = session.decisions.get(decision.id)
    assert [b.accepted for b in decision.bases] == [False, True]
    assert decision.status == "active"


async def test_unknown_needs_review(fixtures_dir: Path) -> None:
    unknowable = ConditionProposal(
        predicate=ManifestUnchanged(actor="ghost-agent"), plain="the ghost agent is unchanged"
    )
    session = await _approved(fixtures_dir, _reporting(unknowable))
    session.decisions.start_run("R-1", "D-1")
    await session.agent("R-1").call("report_store.read_summaries", {})
    assert session.decisions.get("D-1").status == "needs_review"
    await session.agent("R-1").call("report_store.write_draft", {"item": "d", "content": "x"})
    await session.agent("R-1").call("webhook.send_report", {"item": "d"})
    assert session.gateway.outbox.get("A-1").status == "held"


async def test_renew_keeps_epoch(fixtures_dir: Path) -> None:
    session = await _approved(fixtures_dir, _reporting(C1))
    await session.run_to(5)
    session.decisions.renew("D-1")
    d1 = session.decisions.get("D-1")
    assert (d1.status, d1.epoch) == ("active", 2)
    assert session.decisions.graph.conditions["C-1"].last_result is None


async def test_confirm_twice_is_one_event(fixtures_dir: Path) -> None:
    session = Session("s-inv3", fixtures_dir)
    decision = session.decisions.propose(_reporting(C1), "")
    session.decisions.confirm(decision.id)
    session.decisions.confirm(decision.id)
    confirms = [e for e in _kinds(session, "decision.confirmed") if e.decision_id == decision.id]
    assert len(confirms) == 1


async def test_support_standing_approval_is_seeded(fixtures_dir: Path) -> None:
    session = Session("s-inv4", fixtures_dir)
    d0 = session.decisions.get("D-0")
    assert (d0.status, d0.actor) == ("active", "support-agent")
