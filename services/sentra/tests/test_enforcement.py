"""Hold and reject: the gateway enforces what the decision ledger says, in §9.6 order."""

from __future__ import annotations

import asyncio
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sentra.decisions.models import DecisionProposal
from sentra.gateway.controls import GatewayControlAdapter
from sentra.gateway.state import RECOVERY_ACTOR, RunState
from sentra.scenario import Session

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "reporting"


def _calls(session: Session) -> list:
    return [e for e in session.ledger.events() if e.kind == "gateway.call"]


async def test_stale_epoch_rejected_and_webhook_count_unchanged(fixtures_dir: Path) -> None:
    session = Session("s-enf", fixtures_dir)
    await session.run_to(5)
    result = await session.agent("R-1").call("webhook.send_report", {"item": "draft-1"})
    assert (result.ok, result.error) == (False, "stale_epoch")
    assert _calls(session)[-1].payload["reason"] == "stale_epoch"
    await session.gateway.release_due()
    assert session.world.count("webhook.send_report") == 0


async def test_held_send_not_delivered(fixtures_dir: Path) -> None:
    session = Session("s-enf2", fixtures_dir)
    await session.run_to(5)
    await session.gateway.release_due()
    assert session.gateway.outbox.get("A-1").status == "held"
    assert session.world.deliveries == []


async def test_queued_send_released_while_decision_holds(fixtures_dir: Path) -> None:
    session = Session("s-enf3", fixtures_dir)
    await session.run_to(3)
    await session.gateway.release_due()
    assert session.gateway.outbox.get("A-1").status == "delivered"
    assert [d["item"] for d in session.world.deliveries] == ["draft-1"]
    kinds = [e.kind for e in session.ledger.events()][-2:]
    assert kinds == ["action.released", "action.delivered"]


async def test_recovery_only_tool_denied_to_agents(fixtures_dir: Path) -> None:
    session = Session("s-enf4", fixtures_dir)
    await session.run_to(3)
    result = await session.agent("R-1").call(
        "report_store.restore_draft", {"item": "draft-1", "to_version": 0}
    )
    assert (result.ok, result.error) == (False, "recovery_only")
    session.gateway.register_run(RunState(id="X-1", actor=RECOVERY_ACTOR, decision_id="", epoch=0))
    allowed = await session.agent("X-1").call(
        "report_store.restore_draft", {"item": "draft-1", "to_version": 0}
    )
    assert allowed.ok


async def test_control_deny_after_containment(fixtures_dir: Path) -> None:
    session = Session("s-enf5", fixtures_dir)
    await session.run_to(3)
    cause = session.ledger.append("containment.applied", "recovery")
    GatewayControlAdapter(session.gateway, session.bridge).apply(
        "deny-reporting-scratchpad-read", cause
    )
    session.world.grants.add(("reporting-agent", "scratchpad"))
    result = await session.agent("R-1").call("scratchpad.read", {})
    assert (result.ok, result.error) == (False, "control_deny")
    assert session.bridge.projection.applied_controls == ["deny-reporting-scratchpad-read"]


async def test_destructive_needs_live_approval(fixtures_dir: Path) -> None:
    from sentra.gateway.enforce import enforce
    from sentra.gateway.state import ToolCall
    from sentra.tools.catalogue import ToolSpec

    session = Session("s-enf6", fixtures_dir)
    await session.run_to(3)
    wipe = ToolSpec(name="report_store.purge", effect="destructive", resource="report_store/drafts")
    call = ToolCall(run_id="R-1", actor="reporting-agent", tool=wipe, args={"item": "draft-1"})
    state = session.gateway.state
    assert enforce(call, state).reason == "no_live_approval"
    state.live_approvals.add(("reporting-agent", "report_store.purge", "draft-1"))
    assert enforce(call, state).outcome == "forward"
    other = ToolCall(run_id="R-1", actor="reporting-agent", tool=wipe, args={"item": "draft-9"})
    assert enforce(other, state).reason == "no_live_approval"


async def test_operator_suspend_holds_and_fences(fixtures_dir: Path) -> None:
    session = Session("s-enf7", fixtures_dir)
    await session.run_to(3)
    session.decisions.suspend("D-1")
    assert session.gateway.outbox.get("A-1").status == "held"
    result = await session.agent("R-1").call("report_store.read_summaries", {})
    assert result.error == "stale_epoch"


OPS = st.lists(
    st.sampled_from(["start", "read", "send", "suspend", "renew", "release"]),
    min_size=1,
    max_size=14,
)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(ops=OPS)
def test_no_stale_call_gets_through(ops: list[str]) -> None:
    asyncio.run(_interleave(ops))


async def _interleave(ops: list[str]) -> None:
    session = Session("s-prop", FIXTURES)
    decisions = session.decisions
    d = decisions.propose(
        DecisionProposal(statement="Reporting", subject="Reporting", actor="reporting-agent"), ""
    )
    decisions.confirm(d.id)
    session.world.write("draft-1", "report_store/drafts", "r", "reporting-agent")
    runs: list[str] = []
    for op in ops:
        decision = decisions.get(d.id)
        if op == "start" and decision.live:
            runs.append(decisions.start_run(f"R-{len(runs) + 1}", d.id).id)
        elif op in {"read", "send"} and runs:
            run = session.gateway.state.runs[runs[-1]]
            stale = run.epoch < decision.epoch or not decision.live
            before = session.world.count("report_store.read_summaries")
            tool = "report_store.read_summaries" if op == "read" else "webhook.send_report"
            args = {} if op == "read" else {"item": "draft-1"}
            result = await session.agent(run.id).call(tool, args)
            if stale:
                assert not result.ok
                assert session.world.count("report_store.read_summaries") == before
        elif op == "suspend" and decision.live:
            decisions.suspend(d.id)
        elif op == "renew" and decision.status == "suspended":
            decisions.renew(d.id)
        elif op == "release":
            await session.gateway.release_due()
    for event in session.ledger.events():
        if event.kind == "action.released":
            action = session.gateway.outbox.get(event.payload["action_id"])
            run = session.gateway.state.runs[action.run_id]
            assert event.payload["epoch_at_release"] == run.epoch
            assert event.payload["decision_status"] == "active"
