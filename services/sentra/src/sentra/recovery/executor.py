"""The recovery executor: runs a confirmed plan, step by step, through the gateway.

Only a plan whose read-back the operator confirmed reaches this code (INV-7).
Steps run in phase order (PRD §9.8): contain, cut, correct, rebuild. Each step
is recorded as started and then as succeeded, conflict, failed or escalated,
with its evidence. A conflict does not stop the plan: the item is left as the
person left it, and the remaining steps still run.

The executor acts under its own identity and only through registered inverses
and pre-authorised controls (INV-6). It never calls a model (INV-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from sentra.gateway.controls import GatewayControlAdapter
from sentra.ledger import LedgerEvent
from sentra.recovery.compensation import CompensationRegistry, StepResult
from sentra.recovery.plan import (
    ApplyControl,
    CancelRun,
    Compensate,
    Escalate,
    HoldAction,
    PlanStep,
    Preserve,
    Rebuild,
    RecoveryPlan,
    RevokeAccess,
    grant_call_for,
    ordered,
)

if TYPE_CHECKING:
    from sentra.scenario import Session

ConflictStatus = Literal["open", "keep_human", "leave_for_review"]


@dataclass
class Conflict:
    id: str
    plan_id: str
    item: str
    step_event: str
    detail: str
    status: ConflictStatus = "open"


class RecoveryExecutor:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.registry = CompensationRegistry(session.catalogue)
        self.controls = GatewayControlAdapter(session.gateway, session.bridge)
        self.conflicts: dict[str, Conflict] = {}

    async def run(self, plan: RecoveryPlan, confirmed: LedgerEvent) -> list[StepResult]:
        results: list[StepResult] = []
        for index, step in enumerate(ordered(plan.steps)):
            if isinstance(step, Preserve):
                continue
            started = self._record("recovery.step_started", plan, index, step, [confirmed.event_id])
            try:
                result = await self._perform(plan, step, started)
            except Exception as exc:  # a failed step is recorded, never left half-run
                message = str(exc.args[0]) if exc.args else type(exc).__name__
                result = StepResult("failed", f"{step.kind} could not run: {message}")
            kind = f"recovery.step_{result.status}"
            if result.status == "skipped":
                kind = "recovery.step_succeeded"
            event = self._record(
                kind,
                plan,
                index,
                step,
                [started.event_id],
                detail=result.detail,
                evidence=result.evidence,
            )
            if result.status == "conflict":
                conflict = Conflict(
                    id=f"K-{len(self.conflicts) + 1}",
                    plan_id=plan.id,
                    item=str(result.evidence.get("item")),
                    step_event=event.event_id,
                    detail=result.detail,
                )
                self.conflicts[conflict.id] = conflict
            results.append(result)
        return results

    async def _perform(
        self, plan: RecoveryPlan, step: PlanStep, started: LedgerEvent
    ) -> StepResult:
        s = self.session
        if isinstance(step, CancelRun):
            return self._cancel_run(step.run_id, started)
        if isinstance(step, HoldAction):
            action = s.gateway.outbox.get(step.action_id)
            if action.status == "queued":
                s.gateway.hold(action, cites=[started.event_id])
            return StepResult("succeeded", f"{step.action_id} is held.")
        if isinstance(step, ApplyControl):
            applied = s.ledger.append(
                "containment.applied",
                "recovery",
                cites=[started.event_id],
                payload={
                    "capability_id": step.control_id,
                    "finding_id": plan.finding_id,
                    "plan_id": plan.id,
                },
            )
            self.controls.apply(step.control_id, applied)
            return StepResult("succeeded", f"Control {step.control_id} is enforced at the gateway.")
        if isinstance(step, RevokeAccess):
            grant = grant_call_for(s, step)
            if grant is None:
                return StepResult("skipped", f"{step.actor} had no grant on {step.resource}.")
            return await self.registry.compensate(grant, s.recovery_agent())
        if isinstance(step, Compensate):
            call = s.ledger.get(step.call_event)
            if call is None:
                return StepResult("failed", f"There is no recorded call {step.call_event}.")
            return await self.registry.compensate(call, s.recovery_agent())
        if isinstance(step, Rebuild):
            decision = s.decisions.renew(step.decision_id)
            run_id = self._next_run_id(step.decision_id)
            s.decisions.start_run(run_id, decision.id, fresh_context=True)
            return StepResult(
                "succeeded",
                f"{decision.id} renewed. {run_id} started with fresh context.",
                {"run_id": run_id, "sources": list(step.sources)},
            )
        if isinstance(step, Escalate):
            return StepResult("escalated", step.reason)
        return StepResult("skipped", "Nothing to do.")

    def _cancel_run(self, run_id: str, started: LedgerEvent) -> StepResult:
        s = self.session
        run = s.gateway.state.runs[run_id]
        run.status = "cancelled"
        s.ledger.append(
            "run.cancelled",
            "recovery",
            actor=run.actor,
            run_id=run.id,
            decision_id=run.decision_id,
            epoch=run.epoch,
            cites=[started.event_id],
        )
        cancelled: list[str] = []
        for action in s.gateway.outbox.for_run(run_id):
            if action.status in {"queued", "held"}:
                action.status = "cancelled"
                cancelled.append(action.id)
                s.ledger.append(
                    "action.cancelled",
                    "recovery",
                    actor=action.actor,
                    run_id=action.run_id,
                    decision_id=action.decision_id,
                    cites=[started.event_id],
                    payload={"action_id": action.id},
                )
        detail = f"{run_id} cancelled."
        if cancelled:
            detail += f" {', '.join(cancelled)} cancelled before it was sent."
        return StepResult("succeeded", detail, {"cancelled_actions": cancelled})

    def _next_run_id(self, decision_id: str) -> str:
        runs = self.session.gateway.state.runs
        prefix = next(
            (r.id.split("-")[0] for r in runs.values() if r.decision_id == decision_id), "R"
        )
        n = 1
        while f"{prefix}-{n}" in runs:
            n += 1
        return f"{prefix}-{n}"

    def _record(
        self,
        kind: str,
        plan: RecoveryPlan,
        index: int,
        step: PlanStep,
        cites: list[str],
        *,
        detail: str | None = None,
        evidence: dict[str, object] | None = None,
    ) -> LedgerEvent:
        payload: dict[str, object] = {"plan_id": plan.id, "index": index, "step": step.model_dump()}
        if detail is not None:
            payload["detail"] = detail
        if evidence:
            payload["evidence"] = evidence
        return self.session.ledger.append(kind, "recovery", cites=cites, payload=payload)
