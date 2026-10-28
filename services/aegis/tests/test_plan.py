"""Recovery plans: a fixed vocabulary, a validator, and a deterministic read-back."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.recovery.plan import (
    ApplyControl,
    CancelRun,
    Compensate,
    PlanStep,
    Preserve,
    Rebuild,
    RecoveryPlan,
    RevokeAccess,
    complete_plan,
    ordered,
    read_back_plan,
    validate,
)
from aegis.scenario import Session

APPROVED = "report_store/approved_summaries"


@pytest.fixture
async def session(fixtures_dir: Path) -> Session:
    s = Session("s-plan", fixtures_dir)
    await s.run_to(8)
    return s


def _story_steps() -> list[PlanStep]:
    return [
        CancelRun(run_id="R-1"),
        ApplyControl(control_id="deny-reporting-scratchpad-read"),
        RevokeAccess(actor="reporting-agent", resource="scratchpad"),
        Rebuild(decision_id="D-1", sources=[APPROVED]),
        Preserve(scope="support-agent"),
    ]


def _plan(session: Session, steps: list[PlanStep]) -> RecoveryPlan:
    finding = session.bridge.open_findings()[0].id
    return RecoveryPlan(id="P-1", finding_id=finding, dictated_text="", steps=steps)


def _call(session: Session, run_id: str, tool: str) -> str:
    return next(
        e.event_id
        for e in session.ledger.events()
        if e.kind == "gateway.call" and e.run_id == run_id and e.payload["tool"] == tool
    )


async def test_complete_plan_adds_the_implied_draft_correction(session: Session) -> None:
    steps = complete_plan(_story_steps(), session)
    compensations = [s for s in steps if isinstance(s, Compensate)]
    assert compensations == [
        Compensate(call_event=_call(session, "R-1", "report_store.write_draft"))
    ]
    assert [s.kind for s in ordered(steps)] == [
        "CANCEL_RUN",
        "APPLY_CONTROL",
        "REVOKE_ACCESS",
        "COMPENSATE",
        "REBUILD",
        "PRESERVE",
    ]


async def test_storyline_plan_is_valid(session: Session) -> None:
    plan = _plan(session, complete_plan(_story_steps(), session))
    assert validate(plan, session) == []


async def test_validator_rejects_unknown_target(session: Session) -> None:
    errors = validate(_plan(session, [CancelRun(run_id="R-9")]), session)
    assert [e.message for e in errors] == ["There is no run R-9."]


async def test_validator_rejects_severing_control(session: Session) -> None:
    errors = validate(
        _plan(session, [ApplyControl(control_id="block-reporting-webhook-send")]), session
    )
    assert len(errors) == 1
    assert "declared work" in errors[0].message


async def test_preserve_allows_revoking_undeclared_grant(session: Session) -> None:
    steps: list[PlanStep] = [
        RevokeAccess(actor="reporting-agent", resource="scratchpad"),
        Preserve(scope="support-agent"),
    ]
    assert validate(_plan(session, steps), session) == []


async def test_preserve_blocks_touching_declared_work(session: Session) -> None:
    summary_write = _call(session, "S-1", "report_store.write_summary")
    steps: list[PlanStep] = [
        CancelRun(run_id="S-1"),
        Compensate(call_event=summary_write),
        Preserve(scope="support-agent"),
    ]
    messages = [e.message for e in validate(_plan(session, steps), session)]
    assert messages == [
        "Cancelling S-1 would stop work you asked me to keep (support-agent).",
        f"Undoing {summary_write} would change work you asked me to keep (support-agent).",
    ]


async def test_readback_mentions_predicted_conflict(session: Session) -> None:
    plan = _plan(session, complete_plan(_story_steps(), session))
    assert read_back_plan(plan, session).splitlines() == [
        "I will:",
        " 1. Cancel reporting run R-1 and its held external send A-1. "
        "Later calls from R-1 will be rejected.",
        " 2. Cut the route: deny the Reporting Agent reads from the scratchpad "
        "(HIVE's recommended control) and revoke the access the Support Agent granted.",
        " 3. Prepare a correction for draft-1. A person edited draft-1 after the agent wrote it, "
        "so I will not overwrite it. I will ask you.",
        " 4. Renew approval D-1 and start a fresh reporting run "
        "that reads approved summaries only.",
        "I will keep: all Support Agent work.",
        "Cannot be undone: nothing in this plan sends anything.",
        "Interpreted by: grammar (no model call)",
    ]
