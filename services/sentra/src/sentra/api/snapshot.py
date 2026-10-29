"""The console's view of one session: everything it needs to draw the current moment."""

from __future__ import annotations

from typing import Any

from sentra.decisions.models import ConditionProposal
from sentra.interpret.readback import describe_condition
from sentra.ledger import LedgerEvent
from sentra.scenario import Session

#: Which console channel each ledger kind belongs to (PRD §12.3).
_CHANNELS: list[tuple[tuple[str, ...], str]] = [
    (("finding.raised",), "finding"),
    (("alert.raised",), "alert"),
    (("record.closed",), "record"),
    (("verification.check", "containment.verified", "containment.failed"), "verification"),
    (("recovery.", "conflict.", "containment.applied"), "recovery"),
    (("decision.", "condition.", "basis.", "run."), "decision"),
    (("action.",), "action"),
    (("gateway.call", "item.version_changed", "containment.proposed"), "graph"),
]


def channel(event: LedgerEvent) -> str:
    for prefixes, name in _CHANNELS:
        if event.kind.startswith(prefixes):
            return name
    return "ledger"


def snapshot(session: Session) -> dict[str, Any]:
    s = session
    labels = {n.id: n.label for n in s.bridge.manifest.nodes}
    events = s.ledger.events()
    findings = []
    for finding in s.bridge.open_findings():
        plan = s.bridge.plan(finding.id)
        findings.append({**finding.model_dump(), "plan": plan.model_dump()})
    record = next((e.payload for e in reversed(events) if e.kind == "record.closed"), None)
    alerts = [
        e.payload | {"event_id": e.event_id, "decision_id": e.decision_id}
        for e in events
        if e.kind == "alert.raised"
    ]
    return {
        "session_id": s.session_id,
        "labels": {"data": "Fictional data", "mode": "Live sandbox"},
        "manifest_version": s.bridge.manifest.version,
        "beat": s.beat,
        "at_end": s.at_end,
        "storyline": [
            {"n": b["n"], "title": b["title"], "done": i < s.position}
            for i, b in enumerate(s.beats)
        ],
        "architecture": {
            "version": s.bridge.manifest.version,
            "zones": s.bridge.manifest.zones,
            "nodes": [n.model_dump() for n in s.bridge.manifest.nodes],
            "allowed_relationships": [
                r.model_dump() for r in s.bridge.manifest.allowed_relationships
            ],
            "invariants": [i.model_dump() for i in s.bridge.manifest.invariants],
            "control_capabilities": [
                c.model_dump() for c in s.bridge.manifest.control_capabilities
            ],
        },
        "graph": s.bridge.projection.snapshot(),
        "applied_controls": list(s.bridge.projection.applied_controls),
        "findings": findings,
        "alerts": alerts,
        "decisions": [_decision(s, d.id, labels) for d in s.decisions.all()],
        "runs": [
            {
                "id": r.id,
                "actor": r.actor,
                "decision_id": r.decision_id,
                "epoch": r.epoch,
                "status": r.status,
                "fresh_context": r.fresh_context,
            }
            for r in s.gateway.state.runs.values()
            if r.decision_id
        ],
        "actions": [
            {
                "id": a.id,
                "run_id": a.run_id,
                "decision_id": a.decision_id,
                "tool": a.tool,
                "args": a.args,
                "status": a.status,
            }
            for a in s.gateway.outbox.all()
        ],
        "rejected_calls": [
            {
                "event_id": e.event_id,
                "run_id": e.run_id,
                "tool": e.payload["tool"],
                "reason": e.payload.get("reason"),
            }
            for e in events
            if e.kind == "gateway.call" and e.payload.get("outcome") == "rejected"
        ],
        "items": [
            {
                "id": i.id,
                "resource": i.resource,
                "version": i.version,
                "writer": i.writer,
                "content": i.content,
            }
            for i in s.world.items.values()
        ],
        "plans": [p.model_dump() for p in s.recovery.plans.values()],
        "steps": [
            e.payload | {"event_id": e.event_id, "kind": e.kind.removeprefix("recovery.step_")}
            for e in events
            if e.kind.startswith("recovery.step_") and e.kind != "recovery.step_started"
        ],
        "conflicts": [
            {
                "id": c.id,
                "plan_id": c.plan_id,
                "item": c.item,
                "detail": c.detail,
                "status": c.status,
            }
            for c in s.recovery.conflicts.values()
        ],
        "checks": [
            e.payload | {"event_id": e.event_id} for e in events if e.kind == "verification.check"
        ],
        "record": record,
        "deliveries": list(s.world.deliveries),
        "last_seq": events[-1].seq if events else 0,
    }


def _decision(s: Session, decision_id: str, labels: dict[str, str]) -> dict[str, Any]:
    d = s.decisions.get(decision_id)
    conditions = []
    for c in s.decisions.conditions_of(d):
        words, typed = describe_condition(
            ConditionProposal(predicate=c.predicate, plain=c.plain), labels
        )
        conditions.append(
            {
                "id": c.id,
                "plain": c.plain,
                "words": words,
                "typed": typed,
                "last_result": c.last_result,
                "witnesses": c.witnesses,
            }
        )
    return {
        "id": d.id,
        "statement": d.statement,
        "subject": d.subject,
        "actor": d.actor,
        "dictated_text": d.dictated_text,
        "status": d.status,
        "epoch": d.epoch,
        "hold_rule": d.hold_rule,
        "bases": [b.model_dump() for b in d.bases],
        "conditions": conditions,
    }
