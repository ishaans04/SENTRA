"""The final record (PRD §7.4): what was approved, what changed, what was done, what was measured.

In order: the original approval and its condition; the new evidence (the HIVE
finding and the gateway calls it cites); the controls and the operator's
confirmed plan; each step's result, conflicts and failures included; and the
measured outcome from verification. It is built only from the ledger, so it can
be rebuilt from an exported session.

The summary reports what the checks measured, not what the plan intended. A
conflict is reported as a conflict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aegis.recovery.plan import Rebuild, RecoveryPlan

if TYPE_CHECKING:
    from aegis.scenario import Session


def build_record(session: Session, plan: RecoveryPlan) -> dict[str, Any]:
    events = session.ledger.events()
    labels = {n.id: n.label for n in session.bridge.manifest.nodes}
    rebuild = next((s for s in plan.steps if isinstance(s, Rebuild)), None)
    decision = session.decisions.get(rebuild.decision_id) if rebuild else None
    finding = next(
        (
            e.payload
            for e in events
            if e.kind == "finding.raised" and e.payload["id"] == plan.finding_id
        ),
        None,
    )
    steps = [
        {"kind": e.kind.removeprefix("recovery.step_"), **e.payload}
        for e in events
        if e.kind.startswith("recovery.step_")
        and e.kind != "recovery.step_started"
        and e.payload.get("plan_id") == plan.id
    ]
    checks = [
        e.payload
        for e in events
        if e.kind == "verification.check" and e.payload["plan_id"] == plan.id
    ]
    passed = {c["name"] for c in checks if c["passed"]}

    summary: list[str] = []
    if any(e.kind == "action.cancelled" for e in events):
        summary.append("Affected send cancelled.")
    if "route_closed" in passed:
        summary.append("Unexpected access removed.")
    if "replacement_completed" in passed and rebuild is not None:
        summary.append("Report rebuilt from approved sources.")
    if "preserved_work_unchanged" in passed:
        for scope in plan.preserve:
            owner = next((d for d in session.decisions.all() if d.actor == scope), None)
            summary.append(
                f"{owner.subject if owner else labels.get(scope, scope)} work preserved."
            )

    conflicts = [
        f"{c.item}: a person edited it after the agent wrote it. "
        "The human version was kept for review."
        for c in session.recovery.conflicts.values()
        if c.plan_id == plan.id
    ]
    return {
        "plan_id": plan.id,
        "status": plan.status,
        "approval": None
        if decision is None
        else {
            "id": decision.id,
            "statement": decision.statement,
            "dictated_text": decision.dictated_text,
            "conditions": [
                {"id": c.id, "plain": c.plain, "typed": c.predicate.model_dump()}
                for c in session.decisions.conditions_of(decision)
            ],
        },
        "finding": None
        if finding is None
        else {
            "id": finding["id"],
            "rule_id": finding["rule_id"],
            "title": finding["title"],
            "cited_events": finding["evidence_event_ids"],
        },
        "plan": {
            "dictated_text": plan.dictated_text,
            "read_back": plan.read_back,
            "interpreted_by": plan.interpreted_by,
            "controls": [
                e.payload["capability_id"]
                for e in events
                if e.kind == "containment.applied" and e.payload.get("plan_id") == plan.id
            ],
        },
        "steps": steps,
        "checks": checks,
        "summary": summary,
        "conflicts": conflicts,
    }
