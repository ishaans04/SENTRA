"""Verification: the four checks that measure what recovery actually did (AC-09).

Nothing here trusts the plan. Each check measures the session as it is now:

``route_closed``              the engine's rules re-run on the contained graph find no route
``stale_run_rejected``        a probe call from each cancelled run is refused by the gateway
``replacement_completed``     each rebuilt run finished, read only its approved sources,
                              and its send went out
``preserved_work_unchanged``  work the operator asked to keep, and every human edit,
                              is exactly as it was when the plan was confirmed

Each result is recorded as ``checked`` evidence, linked by ``VERIFIED_BY`` to the
plan it measured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sentra.conditions.predicates import ConditionContext, ReadsOnlyFrom
from sentra.recovery.plan import CancelRun, Rebuild, RecoveryPlan

if TYPE_CHECKING:
    from sentra.scenario import Session

Baseline = dict[str, tuple[int, str | None]]


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str
    cites: list[str] = field(default_factory=list)


def snapshot(session: Session) -> Baseline:
    return {item.id: (item.version, item.writer) for item in session.world.items.values()}


async def run_checks(
    session: Session, plan: RecoveryPlan, baseline: Baseline, rebuilt_runs: list[str]
) -> list[Check]:
    return [
        _route_closed(session, plan),
        await _stale_run_rejected(session, plan),
        _replacement_completed(session, plan, rebuilt_runs),
        _preserved_work_unchanged(session, plan, baseline),
    ]


def _route_closed(session: Session, plan: RecoveryPlan) -> Check:
    remaining = [f for f in session.bridge.rerun_rules() if f.rule_id == "PS-001"]
    applied = [
        e.event_id
        for e in session.ledger.events()
        if e.kind == "containment.applied" and e.payload.get("plan_id") == plan.id
    ]
    if remaining:
        return Check(
            "route_closed", False, "The engine still finds the route after containment.", applied
        )
    return Check(
        "route_closed",
        True,
        "The engine re-ran its rules on the contained graph: no route.",
        applied,
    )


async def _stale_run_rejected(session: Session, plan: RecoveryPlan) -> Check:
    probes: list[str] = []
    for step in plan.steps:
        if not isinstance(step, CancelRun):
            continue
        result = await session.agent(step.run_id).call("report_store.read_summaries", {})
        probe = session.ledger.events()[-1]
        probes.append(probe.event_id)
        if result.ok:
            return Check(
                "stale_run_rejected", False, f"A call from {step.run_id} still got through.", probes
            )
    return Check(
        "stale_run_rejected",
        True,
        "A probe call from each cancelled run was rejected by the gateway.",
        probes,
    )


def _replacement_completed(session: Session, plan: RecoveryPlan, rebuilt_runs: list[str]) -> Check:
    cites: list[str] = []
    for step, run_id in zip(
        [s for s in plan.steps if isinstance(s, Rebuild)], rebuilt_runs, strict=False
    ):
        status = session.decisions.graph.runs.get(run_id)
        if status != "completed":
            return Check("replacement_completed", False, f"{run_id} has not finished.", cites)
        decision = session.decisions.get(step.decision_id)
        reads = ReadsOnlyFrom(actor=decision.actor, resources=step.sources).evaluate(
            ConditionContext(
                events=session.ledger.events(),
                bridge=session.bridge,
                decision_id=decision.id,
                epoch=decision.epoch,
            )
        )
        cites.extend(reads.witnesses)
        if reads.result != "HOLDS":
            return Check(
                "replacement_completed", False, f"{run_id} read outside its sources.", cites
            )
        sends = session.gateway.outbox.for_run(run_id)
        if any(a.status != "delivered" for a in sends):
            return Check("replacement_completed", False, f"A send from {run_id} is waiting.", cites)
    return Check(
        "replacement_completed",
        True,
        "The fresh run finished its job from approved sources only, and its report went out.",
        cites,
    )


def _preserved_work_unchanged(session: Session, plan: RecoveryPlan, baseline: Baseline) -> Check:
    keep = set(plan.preserve) | {"teammate"}
    changed = [
        item_id
        for item_id, (version, writer) in baseline.items()
        if writer in keep
        and (
            session.world.items[item_id].version != version
            or session.world.items[item_id].writer != writer
        )
    ]
    if changed:
        return Check(
            "preserved_work_unchanged", False, f"Changed during recovery: {', '.join(changed)}."
        )
    kept = sorted(item for item, (_, writer) in baseline.items() if writer in keep)
    return Check(
        "preserved_work_unchanged",
        True,
        f"Unchanged since the plan was confirmed: {', '.join(kept)}.",
    )
