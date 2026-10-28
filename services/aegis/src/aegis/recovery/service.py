"""The recovery plan lifecycle (PRD §9.5): drafted, read back, confirmed, executed, verified.

A plan is drafted from typed steps (from the grammar or a validated model
output), completed with what it implies, validated, and read back. Only a plan
in ``read_back`` can be confirmed, and confirming re-validates it against the
session as it is now, so a plan that went stale while the operator read it
fails with a plain reason instead of running (Review Focus 5).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from aegis.recovery.executor import Conflict, RecoveryExecutor
from aegis.recovery.plan import (
    Interpreter,
    PlanStep,
    RecoveryPlan,
    complete_plan,
    read_back_plan,
    validate,
)
from aegis.recovery.record import build_record
from aegis.recovery.verify import Baseline, Check, run_checks, snapshot

if TYPE_CHECKING:
    from aegis.scenario import Session

_DONE = frozenset(
    {"confirmed", "executing", "verified", "verified_with_conflicts", "failed", "escalated"}
)
_CHOICES = ("keep_human", "leave_for_review")


class RecoveryError(ValueError):
    """A recovery request that cannot go ahead. The message is shown to the operator."""


class RecoveryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.executor = RecoveryExecutor(session)
        self.plans: dict[str, RecoveryPlan] = {}
        self._baselines: dict[str, Baseline] = {}
        self._rebuilt: dict[str, list[str]] = {}
        self._drafts = 0

    @property
    def conflicts(self) -> dict[str, Conflict]:
        return self.executor.conflicts

    def get(self, plan_id: str) -> RecoveryPlan:
        try:
            return self.plans[plan_id]
        except KeyError:
            raise RecoveryError(f"There is no recovery plan {plan_id}.") from None

    # -- drafting -------------------------------------------------------------

    def draft(
        self,
        steps: list[PlanStep],
        *,
        text: str,
        interpreted_by: Interpreter,
        finding_id: str | None = None,
        plan_id: str | None = None,
    ) -> RecoveryPlan:
        s = self.session
        if plan_id is None:
            # A new instruction replaces any plan still waiting for a read-back, so
            # there is only ever one plan a "Confirm" can mean.
            for earlier in self.plans.values():
                if earlier.status in {"read_back", "invalid", "drafted"}:
                    earlier.status = "abandoned"
                    s.ledger.append(
                        "recovery.plan_abandoned",
                        "operator",
                        payload={"plan_id": earlier.id, "superseded": True},
                    )
        if finding_id is None:
            open_findings = s.bridge.open_findings()
            finding_id = open_findings[0].id if open_findings else None
        plan = RecoveryPlan(
            id=plan_id or f"P-{len(self.plans) + 1}",
            finding_id=finding_id,
            dictated_text=text,
            steps=complete_plan(steps, s),
            interpreted_by=interpreted_by,
        )
        errors = validate(plan, s)
        plan.errors = [e.message for e in errors]
        if errors:
            plan.status = "invalid"
        else:
            plan.read_back = read_back_plan(plan, s)
            plan.status = "read_back"
        self._drafts += 1
        seed = f"{s.session_id}:{plan.id}:{self._drafts}:{plan.read_back}:{plan.errors}"
        plan.revision = hashlib.sha256(seed.encode()).hexdigest()[:12]
        self.plans[plan.id] = plan
        s.ledger.append(
            "recovery.plan_drafted",
            "interpret",
            cites=[e.event_id for e in s.ledger.events() if e.kind == "finding.raised"][-1:],
            payload=plan.model_dump(),
        )
        return plan

    def correct(
        self, plan_id: str, steps: list[PlanStep], *, text: str, interpreted_by: Interpreter
    ) -> RecoveryPlan:
        """The operator dictated a change. The plan is drafted again under the same id."""
        plan = self.get(plan_id)
        if plan.status not in {"read_back", "invalid", "drafted"}:
            raise RecoveryError(f"{plan_id} is {plan.status} and can no longer be corrected.")
        return self.draft(
            steps,
            text=text,
            interpreted_by=interpreted_by,
            finding_id=plan.finding_id,
            plan_id=plan.id,
        )

    def abandon(self, plan_id: str) -> RecoveryPlan:
        plan = self.get(plan_id)
        if plan.status in _DONE:
            raise RecoveryError(f"{plan_id} is {plan.status} and cannot be abandoned.")
        plan.status = "abandoned"
        self.session.ledger.append(
            "recovery.plan_abandoned", "operator", payload={"plan_id": plan.id}
        )
        return plan

    # -- running --------------------------------------------------------------

    def pending(self) -> RecoveryPlan | None:
        """The plan waiting for its read-back to be confirmed, if any (at most one)."""
        waiting = [p for p in self.plans.values() if p.status == "read_back"]
        return waiting[-1] if waiting else None

    async def confirm(self, plan_id: str, revision: str | None = None) -> RecoveryPlan:
        plan = self.get(plan_id)
        if revision is not None and revision != plan.revision:
            raise RecoveryError("The plan changed since you saw it. Please read it again.")
        if plan.status in _DONE:
            return plan
        if plan.status != "read_back":
            raise RecoveryError(f"{plan_id} is {plan.status} and cannot run.")
        errors = validate(plan, self.session)
        if errors:
            plan.status = "invalid"
            plan.errors = [e.message for e in errors]
            raise RecoveryError(" ".join(plan.errors))
        plan.status = "confirmed"
        confirmed = self.session.ledger.append(
            "recovery.plan_confirmed", "operator", payload={"plan_id": plan.id}
        )
        self._baselines[plan.id] = snapshot(self.session)
        plan.status = "executing"
        results = await self.executor.run(plan, confirmed)
        self._rebuilt[plan.id] = [
            str(r.evidence["run_id"]) for r in results if "run_id" in r.evidence
        ]
        if any(r.status == "failed" for r in results):
            plan.status = "failed"
        return plan

    async def verify(self, plan_id: str) -> list[Check]:
        plan = self.get(plan_id)
        if plan.status not in {"executing", "failed"}:
            raise RecoveryError(f"{plan_id} is {plan.status}; there is nothing to verify.")
        s = self.session
        checks = await run_checks(s, plan, self._baselines[plan.id], self._rebuilt.get(plan.id, []))
        for check in checks:
            event = s.ledger.append(
                "verification.check",
                "verification",
                cites=check.cites,
                payload={
                    "plan_id": plan.id,
                    "name": check.name,
                    "passed": check.passed,
                    "detail": check.detail,
                },
            )
            s.ledger.append(
                "evidence.recorded",
                "verification",
                cites=[event.event_id],
                payload={
                    "id": f"E-{len(s.decisions.graph.evidence) + 1}",
                    "kind": "checked",
                    "source": f"check:{check.name}",
                    "applies": check.passed,
                    "cites": check.cites,
                    "verifies": plan.id,
                },
            )
        route = next(c for c in checks if c.name == "route_closed")
        s.ledger.append(
            "containment.verified" if route.passed else "containment.failed",
            "verification",
            cites=route.cites,
            payload={"plan_id": plan.id, "finding_id": plan.finding_id},
        )
        if plan.status == "failed" or not all(c.passed for c in checks):
            plan.status = "failed"
        elif any(c.plan_id == plan.id for c in self.conflicts.values()):
            plan.status = "verified_with_conflicts"
        else:
            plan.status = "verified"
        return checks

    def close_record(self, plan_id: str) -> dict[str, Any]:
        plan = self.get(plan_id)
        if plan.status not in {"verified", "verified_with_conflicts", "failed", "escalated"}:
            raise RecoveryError(f"{plan_id} is {plan.status}; verify it before closing the record.")
        record = build_record(self.session, plan)
        self.session.ledger.append("record.closed", "recovery", payload=record)
        return record

    def resolve_conflict(self, conflict_id: str, choice: str) -> Conflict:
        conflict = self.conflicts.get(conflict_id)
        if conflict is None:
            raise RecoveryError(f"There is no conflict {conflict_id}.")
        if choice not in _CHOICES:
            raise RecoveryError("Choose keep_human or leave_for_review. Nothing is overwritten.")
        conflict.status = "keep_human" if choice == "keep_human" else "leave_for_review"
        self.session.ledger.append(
            "conflict.resolved",
            "operator",
            cites=[conflict.step_event],
            payload={"conflict_id": conflict.id, "item": conflict.item, "choice": choice},
        )
        return conflict
