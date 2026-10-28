"""Recovery plans: the fixed vocabulary of pre-authorised steps (PRD §11.7).

Whatever produced a plan, the grammar or a model, it is only a list of these
steps with ids filled in. ``validate`` checks every id against the session and
every control against the HIVE planner's verdict before anything is read back,
so a model can propose a plan but can never make an unsafe one runnable.

``PRESERVE`` is a constraint, not an action. It protects the scope's **declared**
work: its runs, and what it produced in resources the manifest declares for it.
Cutting an undeclared hop on the finding's route, such as revoking the
scratchpad grant the Support Agent made, does not touch declared work (D11).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from aegis.interpret.readback import INTERPRETED_BY

if TYPE_CHECKING:
    from aegis.ledger import LedgerEvent
    from aegis.scenario import Session

Phase = Literal["contain", "cut", "correct", "rebuild", "escalate", "constraint"]
PlanStatus = Literal[
    "drafted",
    "invalid",
    "read_back",
    "confirmed",
    "executing",
    "verified",
    "verified_with_conflicts",
    "failed",
    "escalated",
    "abandoned",
]
Interpreter = Literal["gemini", "groq", "grammar", "recorded"]

_EFFECT_AS_ACTION = {"read": "read", "write": "write", "send": "send"}


class _Step(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CancelRun(_Step):
    kind: Literal["CANCEL_RUN"] = "CANCEL_RUN"
    run_id: str


class HoldAction(_Step):
    kind: Literal["HOLD_ACTION"] = "HOLD_ACTION"
    action_id: str


class ApplyControl(_Step):
    kind: Literal["APPLY_CONTROL"] = "APPLY_CONTROL"
    control_id: str


class RevokeAccess(_Step):
    kind: Literal["REVOKE_ACCESS"] = "REVOKE_ACCESS"
    actor: str
    resource: str


class Compensate(_Step):
    kind: Literal["COMPENSATE"] = "COMPENSATE"
    #: The ledger id of the executed ``gateway.call`` to undo.
    call_event: str


class Rebuild(_Step):
    kind: Literal["REBUILD"] = "REBUILD"
    decision_id: str
    sources: list[str]


class Preserve(_Step):
    kind: Literal["PRESERVE"] = "PRESERVE"
    #: An actor id or a run id.
    scope: str


class Escalate(_Step):
    kind: Literal["ESCALATE"] = "ESCALATE"
    reason: str


PlanStep = Annotated[
    CancelRun
    | HoldAction
    | ApplyControl
    | RevokeAccess
    | Compensate
    | Rebuild
    | Preserve
    | Escalate,
    Field(discriminator="kind"),
]

PHASE: dict[str, Phase] = {
    "CANCEL_RUN": "contain",
    "HOLD_ACTION": "contain",
    "APPLY_CONTROL": "cut",
    "REVOKE_ACCESS": "cut",
    "COMPENSATE": "correct",
    "REBUILD": "rebuild",
    "ESCALATE": "escalate",
    "PRESERVE": "constraint",
}
_ORDER: list[Phase] = ["contain", "cut", "correct", "rebuild", "escalate", "constraint"]


class RecoveryPlan(BaseModel):
    id: str
    finding_id: str | None = None
    dictated_text: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    read_back: str = ""
    status: PlanStatus = "drafted"
    interpreted_by: Interpreter = "grammar"
    errors: list[str] = Field(default_factory=list)
    #: Changes whenever the read-back changes. Confirm must name the one seen.
    revision: str = ""

    @property
    def preserve(self) -> list[str]:
        return [s.scope for s in self.steps if isinstance(s, Preserve)]


@dataclass(frozen=True)
class PlanError:
    step: int
    message: str


def ordered(steps: list[PlanStep]) -> list[PlanStep]:
    """Steps in execution order: contain, cut, correct, rebuild; stable within a phase."""
    return sorted(steps, key=lambda s: _ORDER.index(PHASE[s.kind]))


# -- completing ---------------------------------------------------------------


def complete_plan(steps: list[PlanStep], session: Session) -> list[PlanStep]:
    """Add what an instruction implies but does not say.

    Cancelling a run implies correcting what it changed: every executed write by
    that run that has a registered inverse gets a ``COMPENSATE`` step. Whether
    that correction can run safely is decided later, by the version check.
    """
    result = list(steps)
    have = {s.call_event for s in steps if isinstance(s, Compensate)}
    for step in steps:
        if not isinstance(step, CancelRun):
            continue
        for call in _executed_calls(session, step.run_id):
            spec = session.catalogue.get(str(call.payload["tool"]))
            if spec.effect != "write" or spec.inverse in (None, "irreversible"):
                continue
            if call.event_id not in have:
                have.add(call.event_id)
                result.append(Compensate(call_event=call.event_id))
    return ordered(result)


# -- validating ---------------------------------------------------------------


def validate(plan: RecoveryPlan, session: Session) -> list[PlanError]:
    errors: list[PlanError] = []
    manifest = session.bridge.manifest
    nodes = {n.id for n in manifest.nodes}
    runs = session.gateway.state.runs
    preserve = _preserved_actors(plan, session)
    viability = _control_verdicts(plan, session)

    for index, step in enumerate(plan.steps):

        def fail(message: str, at: int = index) -> None:
            errors.append(PlanError(at, message))

        if isinstance(step, CancelRun):
            run = runs.get(step.run_id)
            if run is None:
                fail(f"There is no run {step.run_id}.")
            elif run.status in {"completed", "cancelled"}:
                fail(f"{step.run_id} has already finished, so there is nothing to stop.")
            elif run.actor in preserve or step.run_id in preserve:
                fail(
                    f"Cancelling {step.run_id} would stop work you asked me to keep ({run.actor})."
                )
        elif isinstance(step, HoldAction):
            try:
                session.gateway.outbox.get(step.action_id)
            except KeyError:
                fail(f"There is no queued action {step.action_id}.")
        elif isinstance(step, ApplyControl):
            capability = next(
                (c for c in manifest.control_capabilities if c.id == step.control_id), None
            )
            if capability is None:
                fail(f"{step.control_id} is not a pre-authorised control.")
                continue
            verdict = viability.get(step.control_id)
            if verdict is not None and not verdict:
                fail(f"{capability.label} would sever declared work, so HIVE rejected it.")
            if (
                capability.type == "block_edge"
                and capability.source in preserve
                and manifest.allows(
                    str(capability.source), str(capability.action), capability.target
                )
            ):
                fail(f"{capability.label} would change work you asked me to keep.")
        elif isinstance(step, RevokeAccess):
            if step.resource not in nodes or step.actor not in nodes:
                fail(f"I do not know {step.actor} on {step.resource}.")
            elif _grant_call(session, step) is None:
                fail(f"Nobody granted {step.actor} access to {step.resource}.")
            elif step.actor in preserve and manifest.allows(step.actor, "read", step.resource):
                fail(f"Revoking {step.actor} would change work you asked me to keep.")
        elif isinstance(step, Compensate):
            call = session.ledger.get(step.call_event)
            if call is None or call.kind != "gateway.call":
                fail(f"There is no recorded call {step.call_event}.")
                continue
            spec = session.catalogue.get(str(call.payload["tool"]))
            action = _EFFECT_AS_ACTION.get(spec.effect)
            declared = action is not None and manifest.allows(
                str(call.actor), action, spec.resource
            )
            if call.actor in preserve and declared:
                fail(
                    f"Undoing {step.call_event} would change work you asked me to keep "
                    f"({call.actor})."
                )
        elif isinstance(step, Rebuild):
            decision = session.decisions.graph.decisions.get(step.decision_id)
            if decision is None:
                fail(f"There is no approval {step.decision_id}.")
            elif decision.status not in {"suspended", "active"}:
                fail(
                    f"Approval {step.decision_id} is {decision.status.replace('_', ' ')}, "
                    "so it cannot be renewed for a rebuild."
                )
            unknown = [s for s in step.sources if s not in nodes]
            if unknown:
                fail(f"I do not know the source {', '.join(unknown)}.")
        elif isinstance(step, Preserve) and step.scope not in nodes and step.scope not in runs:
            fail(f"I do not know what {step.scope} is, so I cannot keep it.")
    return errors


def _preserved_actors(plan: RecoveryPlan, session: Session) -> set[str]:
    scopes = set(plan.preserve)
    for scope in list(scopes):
        run = session.gateway.state.runs.get(scope)
        if run is not None:
            scopes.add(run.actor)
    return scopes


def _control_verdicts(plan: RecoveryPlan, session: Session) -> dict[str, bool]:
    if not plan.finding_id or session.bridge.finding(plan.finding_id) is None:
        return {}
    hive_plan = session.bridge.plan(plan.finding_id)
    return {c.capability_id: c.viable for c in hive_plan.candidates}


def _executed_calls(session: Session, run_id: str) -> list[LedgerEvent]:
    return [
        e
        for e in session.ledger.events()
        if e.kind == "gateway.call"
        and e.run_id == run_id
        and e.payload.get("outcome") == "executed"
    ]


def _grant_call(session: Session, step: RevokeAccess) -> LedgerEvent | None:
    for event in session.ledger.events():
        if (
            event.kind == "gateway.call"
            and event.payload.get("outcome") == "executed"
            and session.catalogue.get(str(event.payload["tool"])).effect == "grant"
            and event.payload.get("resource") == step.resource
            and (event.payload.get("args") or {}).get("grantee") == step.actor
        ):
            return event
    return None


def grant_call_for(session: Session, step: RevokeAccess) -> LedgerEvent | None:
    """The executed call that made the grant *step* revokes."""
    return _grant_call(session, step)


# -- reading back -------------------------------------------------------------


def read_back_plan(plan: RecoveryPlan, session: Session) -> str:
    labels = {n.id: n.label for n in session.bridge.manifest.nodes}
    lines = ["I will:"]
    steps = ordered(plan.steps)
    numbered: list[str] = []

    contain = [s for s in steps if PHASE[s.kind] == "contain"]
    for step in contain:
        if isinstance(step, CancelRun):
            run = session.gateway.state.runs[step.run_id]
            subject = session.decisions.get(run.decision_id).subject.lower()
            open_sends = [
                a.id
                for a in session.gateway.outbox.for_run(step.run_id)
                if a.status in {"queued", "held"}
            ]
            sends = ""
            if open_sends:
                state = session.gateway.outbox.get(open_sends[0]).status
                sends = f" and its {state} external send {', '.join(open_sends)}"
            numbered.append(
                f"Cancel {subject} run {step.run_id}{sends}. "
                f"Later calls from {step.run_id} will be rejected."
            )
        elif isinstance(step, HoldAction):
            numbered.append(f"Hold queued action {step.action_id}.")

    cut: list[str] = []
    recommended = None
    if plan.finding_id and session.bridge.finding(plan.finding_id) is not None:
        recommended = session.bridge.plan(plan.finding_id).recommended_capability_id
    for step in steps:
        if isinstance(step, ApplyControl):
            capability = next(
                c for c in session.bridge.manifest.control_capabilities if c.id == step.control_id
            )
            label = capability.label[0].lower() + capability.label[1:]
            note = " (HIVE's recommended control)" if step.control_id == recommended else ""
            cut.append(f"{label}{note}")
        elif isinstance(step, RevokeAccess):
            grant = _grant_call(session, step)
            granter = labels.get(str(grant.actor), str(grant.actor)) if grant else "someone"
            cut.append(f"revoke the access the {granter} granted")
    if cut:
        numbered.append("Cut the route: " + " and ".join(cut) + ".")

    for step in steps:
        if isinstance(step, Compensate):
            numbered.append(_compensation_line(step, session))

    for step in steps:
        if isinstance(step, Rebuild):
            decision = session.decisions.get(step.decision_id)
            sources = " and ".join(labels.get(s, s).lower() for s in step.sources)
            numbered.append(
                f"Renew approval {step.decision_id} and start a fresh {decision.subject.lower()} "
                f"run that reads {sources} only."
            )
    for step in steps:
        if isinstance(step, Escalate):
            numbered.append(f"Stop and ask a person: {step.reason}")

    lines.extend(f" {i}. {text}" for i, text in enumerate(numbered, start=1))
    kept = [labels.get(scope, scope) for scope in plan.preserve]
    if kept:
        lines.append("I will keep: " + ", ".join(f"all {k} work" for k in kept) + ".")
    lines.append("Cannot be undone: nothing in this plan sends anything.")
    lines.append(f"Interpreted by: {INTERPRETED_BY.get(plan.interpreted_by, plan.interpreted_by)}")
    return "\n".join(lines)


def _compensation_line(step: Compensate, session: Session) -> str:
    call = session.ledger.get(step.call_event)
    assert call is not None
    item_id = str((call.payload.get("args") or {}).get("item", call.payload["resource"]))
    produced = int((call.payload.get("result") or {}).get("version", 0))
    item = session.world.items.get(item_id)
    if item is not None and (item.version != produced or item.writer != call.actor):
        return (
            f"Prepare a correction for {item_id}. A person edited {item_id} after the agent "
            "wrote it, so I will not overwrite it. I will ask you."
        )
    return f"Undo the agent's change to {item_id}, after checking nobody has changed it since."
