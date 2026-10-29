"""Executing a confirmed plan, verifying it, and closing the record."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentra.recovery.plan import ApplyControl, CancelRun, PlanStep, Preserve, Rebuild, RevokeAccess
from sentra.recovery.service import RecoveryError
from sentra.scenario import Session

APPROVED = "report_store/approved_summaries"
STEPS: list[PlanStep] = [
    CancelRun(run_id="R-1"),
    ApplyControl(control_id="deny-reporting-scratchpad-read"),
    RevokeAccess(actor="reporting-agent", resource="scratchpad"),
    Rebuild(decision_id="D-1", sources=[APPROVED]),
    Preserve(scope="support-agent"),
]


def _kinds(session: Session, kind: str) -> list:
    return [e for e in session.ledger.events() if e.kind == kind]


async def _replacement(session: Session) -> None:
    agent = session.agent("R-2")
    await agent.call("report_store.read_summaries", {})
    await agent.call("report_store.write_draft", {"item": "draft-2", "content": "Rebuilt report."})
    await agent.call("webhook.send_report", {"item": "draft-2"})
    await session.gateway.release_due()
    session.decisions.complete_run("R-2")


@pytest.fixture
async def session(fixtures_dir: Path) -> Session:
    s = Session("s-rec", fixtures_dir)
    await s.run_to(8)
    return s


async def test_confirmed_plan_contains_cuts_and_rebuilds(session: Session) -> None:
    plan = session.recovery.draft(STEPS, text="(typed)", interpreted_by="grammar")
    assert plan.status == "read_back"
    await session.recovery.confirm(plan.id)

    assert session.gateway.state.runs["R-1"].status == "cancelled"
    assert session.gateway.outbox.get("A-1").status == "cancelled"
    assert session.bridge.projection.applied_controls == ["deny-reporting-scratchpad-read"]
    assert ("reporting-agent", "scratchpad") not in session.world.grants
    conflicts = _kinds(session, "recovery.step_conflict")
    assert len(conflicts) == 1 and conflicts[0].payload["evidence"]["item"] == "draft-1"
    assert session.world.items["draft-1"].writer == "teammate"
    d1 = session.decisions.get("D-1")
    assert (d1.status, d1.epoch) == ("active", 2)
    r2 = session.gateway.state.runs["R-2"]
    assert (r2.epoch, r2.fresh_context, r2.status) == (2, True, "running")


async def test_verification_and_record(session: Session) -> None:
    plan = session.recovery.draft(STEPS, text="(typed)", interpreted_by="grammar")
    await session.recovery.confirm(plan.id)
    await _replacement(session)
    assert session.gateway.outbox.get("A-2").status == "delivered"

    checks = await session.recovery.verify(plan.id)
    assert [(c.name, c.passed) for c in checks] == [
        ("route_closed", True),
        ("stale_run_rejected", True),
        ("replacement_completed", True),
        ("preserved_work_unchanged", True),
    ]
    assert session.recovery.get(plan.id).status == "verified_with_conflicts"
    assert len(_kinds(session, "containment.verified")) == 1
    checked = [e for e in session.decisions.graph.evidence.values() if e.kind == "checked"]
    assert len(checked) == 4

    record = session.recovery.close_record(plan.id)
    assert record["summary"] == [
        "Affected send cancelled.",
        "Unexpected access removed.",
        "Report rebuilt from approved sources.",
        "Support work preserved.",
    ]
    assert record["conflicts"] == [
        "draft-1: a person edited it after the agent wrote it. "
        "The human version was kept for review."
    ]
    assert record["approval"]["id"] == "D-1"
    assert record["finding"]["rule_id"] == "PS-001"
    assert _kinds(session, "record.closed")[0].payload == record


async def test_conflict_resolution_never_overwrites(session: Session) -> None:
    plan = session.recovery.draft(STEPS, text="(typed)", interpreted_by="grammar")
    await session.recovery.confirm(plan.id)
    [conflict] = session.recovery.conflicts.values()
    session.recovery.resolve_conflict(conflict.id, "keep_human")
    assert session.recovery.conflicts[conflict.id].status == "keep_human"
    assert session.world.items["draft-1"].writer == "teammate"
    with pytest.raises(RecoveryError, match="keep_human or leave_for_review"):
        session.recovery.resolve_conflict(conflict.id, "overwrite")


async def test_confirm_twice_runs_once(session: Session) -> None:
    plan = session.recovery.draft(STEPS, text="(typed)", interpreted_by="grammar")
    await session.recovery.confirm(plan.id)
    await session.recovery.confirm(plan.id)
    assert len(_kinds(session, "recovery.plan_confirmed")) == 1
    assert len(_kinds(session, "run.cancelled")) == 1


async def test_confirm_after_the_run_finished_fails_plainly(session: Session) -> None:
    plan = session.recovery.draft(STEPS, text="(typed)", interpreted_by="grammar")
    session.gateway.state.runs["R-1"].status = "cancelled"  # ended while the operator read
    with pytest.raises(RecoveryError, match="R-1 has already finished"):
        await session.recovery.confirm(plan.id)
    assert session.recovery.get(plan.id).status == "invalid"
    assert not [e for e in session.ledger.events() if e.kind == "recovery.plan_confirmed"]


async def test_a_second_draft_supersedes_the_first(session: Session) -> None:
    first = session.recovery.draft(STEPS, text="(typed)", interpreted_by="grammar")
    second = session.recovery.draft(STEPS, text="(typed again)", interpreted_by="grammar")
    assert session.recovery.get(first.id).status == "abandoned"
    assert session.recovery.pending() == second
    with pytest.raises(RecoveryError, match="abandoned"):
        await session.recovery.confirm(first.id)


async def test_invalid_plan_is_never_read_back(session: Session) -> None:
    plan = session.recovery.draft([CancelRun(run_id="R-9")], text="", interpreted_by="grammar")
    assert plan.status == "invalid"
    assert plan.errors == ["There is no run R-9."]
    with pytest.raises(RecoveryError, match="cannot run"):
        await session.recovery.confirm(plan.id)


async def test_abandon(session: Session) -> None:
    plan = session.recovery.draft(STEPS, text="", interpreted_by="grammar")
    session.recovery.abandon(plan.id)
    assert session.recovery.get(plan.id).status == "abandoned"
    assert session.gateway.state.runs["R-1"].status == "stale"
