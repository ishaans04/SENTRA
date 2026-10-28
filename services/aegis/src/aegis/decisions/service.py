"""Decisions over time: propose, confirm, invalidate, suspend, renew.

This is the AEGIS half of the loop. When HIVE raises a finding, or a call
touches a condition's subject, every live decision's conditions are re-evaluated
against the current epoch's evidence (PRD §9.7):

- a condition that FAILS withdraws every basis containing it;
- if no accepted basis remains, the decision is suspended and its epoch moves
  forward by one. Runs started at the old epoch are now stale, and the gateway
  rejects their calls. Under the pre-authorised hold rule, the decision's queued
  sends are held. One alert is raised per finding.
- a condition that is UNKNOWN puts the decision in Needs review and holds its
  queued sends, while other calls continue.

The forward walk is the AEGIS invalidation cascade, without confidence or taint:
here a dependency either stands or it does not.

Renewal does not move the epoch. The suspension already fenced the old runs
off; renewal only lets new runs start at the current epoch.
"""

from __future__ import annotations

from typing import Any

from aegis.conditions.predicates import ConditionContext, Evaluation
from aegis.decisions.graph import DecisionGraph
from aegis.decisions.models import (
    Basis,
    Condition,
    ConditionProposal,
    Decision,
    DecisionProposal,
)
from aegis.gateway.server import Gateway
from aegis.gateway.state import RunState
from aegis.hive_bridge import HiveBridge
from aegis.ledger import LedgerEvent, Producer, SessionLedger
from hive_core.domain.models import Finding

_VERB = {"read": "read", "write": "written to", "send": "sent to", "grant": "granted access to"}


class DecisionError(ValueError):
    """An operation that the decision's current state does not allow."""


class DecisionService:
    def __init__(self, ledger: SessionLedger, bridge: HiveBridge, gateway: Gateway) -> None:
        self.ledger = ledger
        self.bridge = bridge
        self.gateway = gateway
        self.graph = DecisionGraph()
        ledger.listeners.append(self.graph.apply)
        gateway.state.decisions = self.graph.decisions
        self._alerted: set[str] = set()
        self._bases = 0

    # -- reading --------------------------------------------------------------

    def get(self, decision_id: str) -> Decision:
        try:
            return self.graph.decisions[decision_id]
        except KeyError:
            raise DecisionError(f"No decision {decision_id!r}.") from None

    def all(self) -> list[Decision]:
        return list(self.graph.decisions.values())

    def conditions_of(self, decision: Decision) -> list[Condition]:
        ids = [c for basis in decision.bases for c in basis.conditions]
        return [self.graph.conditions[c] for c in dict.fromkeys(ids)]

    # -- operator actions -----------------------------------------------------

    def propose(
        self,
        proposal: DecisionProposal,
        dictated_text: str,
        producer: Producer = "interpret",
        *,
        extra_bases: list[list[ConditionProposal]] | None = None,
    ) -> Decision:
        """Record a proposed decision. Each extra basis is an independent reason to stand."""
        decision_id = f"D-{len(self.graph.decisions)}"
        groups = [proposal.conditions, *(extra_bases or [])]
        conditions: list[Condition] = []
        bases: list[Basis] = []
        for group in groups:
            made = self._conditions(group, start=len(self.graph.conditions) + len(conditions) + 1)
            conditions.extend(made)
            bases.append(self._basis(made))
        decision = Decision(
            id=decision_id,
            statement=proposal.statement,
            subject=proposal.subject,
            actor=proposal.actor,
            dictated_text=dictated_text,
            bases=bases,
            hold_rule=proposal.hold_rule,
        )
        self._emit(
            "decision.proposed",
            producer,
            decision_id=decision_id,
            payload={
                "decision": decision.model_dump(),
                "conditions": [c.model_dump() for c in conditions],
            },
        )
        return self.get(decision_id)

    def confirm(self, decision_id: str) -> Decision:
        decision = self.get(decision_id)
        if decision.status == "active":
            return decision
        if decision.status not in {"proposed", "needs_review"}:
            raise DecisionError(f"{decision_id} is {decision.status} and cannot be confirmed.")
        self._emit("decision.confirmed", "operator", decision_id=decision_id, epoch=decision.epoch)
        return decision

    def reject(self, decision_id: str) -> Decision:
        decision = self.get(decision_id)
        if decision.status != "proposed":
            raise DecisionError(f"{decision_id} is {decision.status} and cannot be rejected.")
        self._emit("decision.discarded", "operator", decision_id=decision_id)
        return decision

    def renew(self, decision_id: str) -> Decision:
        decision = self.get(decision_id)
        if decision.status == "active":
            return decision
        if decision.status != "suspended":
            raise DecisionError(f"{decision_id} is {decision.status} and cannot be renewed.")
        self._emit("decision.renewed", "operator", decision_id=decision_id, epoch=decision.epoch)
        return decision

    def suspend(self, decision_id: str) -> Decision:
        """The operator suspends a live decision by hand (PRD §9.2)."""
        decision = self.get(decision_id)
        if decision.status == "suspended":
            return decision
        if not decision.live:
            raise DecisionError(f"{decision_id} is {decision.status} and cannot be suspended.")
        self._suspend(decision, None, None, {})
        return decision

    def withdraw(self, decision_id: str) -> Decision:
        decision = self.get(decision_id)
        if decision.status in {"withdrawn", "discarded"}:
            return decision
        self._emit("decision.withdrawn", "operator", decision_id=decision_id, epoch=decision.epoch)
        return decision

    def start_run(self, run_id: str, decision_id: str, *, fresh_context: bool = False) -> RunState:
        decision = self.get(decision_id)
        if not decision.live:
            raise DecisionError(f"{decision_id} is {decision.status}; no run can start under it.")
        run = self.gateway.register_run(
            RunState(
                id=run_id,
                actor=decision.actor,
                decision_id=decision_id,
                epoch=decision.epoch,
                fresh_context=fresh_context,
            )
        )
        self._emit(
            "run.started",
            "gateway",
            actor=decision.actor,
            run_id=run_id,
            decision_id=decision_id,
            epoch=decision.epoch,
            payload={"fresh_context": fresh_context},
        )
        return run

    def complete_run(self, run_id: str) -> RunState:
        """A run finished its job."""
        run = self.gateway.state.runs[run_id]
        if run.status != "running":
            raise DecisionError(f"{run_id} is {run.status} and cannot complete.")
        run.status = "completed"
        self._emit(
            "run.completed",
            "gateway",
            actor=run.actor,
            run_id=run.id,
            decision_id=run.decision_id,
            epoch=run.epoch,
        )
        return run

    # -- reacting to evidence -------------------------------------------------

    def on_finding(self, finding: Finding, raised: LedgerEvent) -> None:
        for decision in list(self.graph.decisions.values()):
            if decision.live:
                self.reevaluate(decision.id, cause=raised, finding=finding)

    def on_call(self, call: LedgerEvent) -> None:
        if call.payload.get("outcome") != "executed":
            return
        for decision in list(self.graph.decisions.values()):
            if decision.live and decision.actor == call.actor:
                self.reevaluate(decision.id, cause=call, quiet=True)

    def reevaluate(
        self,
        decision_id: str,
        *,
        cause: LedgerEvent | None,
        finding: Finding | None = None,
        quiet: bool = False,
    ) -> Decision:
        """Re-check every condition of *decision_id*'s accepted bases (PRD §9.7)."""
        decision = self.get(decision_id)
        ctx = ConditionContext(
            events=self.ledger.events(),
            bridge=self.bridge,
            decision_id=decision.id,
            epoch=decision.epoch,
        )
        results: dict[str, Evaluation] = {}
        for basis in decision.bases:
            if not basis.accepted:
                continue
            for condition_id in basis.conditions:
                if condition_id in results:
                    continue
                condition = self.graph.conditions[condition_id]
                outcome = condition.predicate.evaluate(ctx)
                results[condition_id] = outcome
                if quiet and outcome.result == condition.last_result:
                    continue
                self._emit(
                    "condition.evaluated",
                    "aegis",
                    decision_id=decision.id,
                    epoch=decision.epoch,
                    cites=[*outcome.witnesses, *([cause.event_id] if cause else [])],
                    payload={
                        "condition_id": condition_id,
                        "result": outcome.result,
                        "witnesses": outcome.witnesses,
                        "cause": finding.id if finding else (cause.event_id if cause else None),
                    },
                )

        failed = [
            b
            for b in decision.bases
            if b.accepted and any(results[c].result == "FAILS" for c in b.conditions)
        ]
        for basis in failed:
            self._emit(
                "basis.withdrawn",
                "aegis",
                decision_id=decision.id,
                cites=[cause.event_id] if cause else [],
                payload={"basis_id": basis.id},
            )
        if failed and not any(b.accepted for b in decision.bases):
            self._suspend(decision, cause, finding, results)
        elif decision.status == "active" and any(
            results[c].result == "UNKNOWN"
            for b in decision.bases
            if b.accepted
            for c in b.conditions
        ):
            self._emit(
                "decision.needs_review",
                "aegis",
                decision_id=decision.id,
                epoch=decision.epoch,
                cites=[cause.event_id] if cause else [],
            )
            self._hold_sends(decision, cause)
        return decision

    # -- internals ------------------------------------------------------------

    def _suspend(
        self,
        decision: Decision,
        cause: LedgerEvent | None,
        finding: Finding | None,
        results: dict[str, Evaluation],
    ) -> None:
        new_epoch = decision.epoch + 1
        dependents = self.graph.dependents(decision.id)
        self._emit(
            "decision.suspended",
            "aegis",
            decision_id=decision.id,
            epoch=new_epoch,
            cites=[cause.event_id] if cause else [],
            payload={"new_epoch": new_epoch, "needs_review": dependents},
        )
        for run in self.gateway.state.runs.values():
            if run.decision_id == decision.id and run.epoch < new_epoch and run.status == "running":
                run.status = "stale"
        held = self._hold_sends(decision, cause)
        if finding is not None and finding.id not in self._alerted:
            self._alerted.add(finding.id)
            self._emit(
                "alert.raised",
                "aegis",
                decision_id=decision.id,
                cites=[cause.event_id] if cause else [],
                payload={
                    "finding_id": finding.id,
                    "held_actions": held,
                    "text": self._alert_text(decision, results, held),
                },
            )

    def _hold_sends(self, decision: Decision, cause: LedgerEvent | None) -> list[str]:
        held: list[str] = []
        if not decision.hold_rule:
            return held
        for action in self.gateway.outbox.all():
            if action.decision_id == decision.id and action.status == "queued":
                self.gateway.hold(action, cites=[cause.event_id] if cause else [])
                held.append(action.id)
        return held

    def _alert_text(
        self, decision: Decision, results: dict[str, Evaluation], held: list[str]
    ) -> str:
        failing = next(
            (c for c, r in results.items() if r.result == "FAILS"), next(iter(results), None)
        )
        condition = self.graph.conditions[failing] if failing else None
        plain = condition.plain if condition else "its conditions hold"
        observed = "changed what it touches"
        witnesses = results[failing].witnesses if failing else []
        call = self.ledger.get(witnesses[0]) if witnesses else None
        if call is not None and call.kind == "gateway.call":
            observed = f"{_VERB.get(str(call.payload['effect']), 'used')} {self._describe(call)}"
        if held:
            affected = (
                "An external report is queued"
                if len(held) == 1
                else f"{len(held)} external reports are queued"
            )
        else:
            affected = "No queued action is affected"
        return (
            f"{decision.subject} was approved on the condition that {plain}. "
            f"It has now {observed}. {affected}. This run needs review."
        )

    def _describe(self, call: LedgerEvent) -> str:
        resource = str(call.payload["resource"])
        node = next((n for n in self.bridge.manifest.nodes if n.id == resource), None)
        if node is None:
            return resource
        if node.registration == "unregistered":
            return f"an undeclared {node.label.lower()}"
        return node.label.lower()

    def _conditions(self, proposals: list[ConditionProposal], start: int) -> list[Condition]:
        return [
            Condition(id=f"C-{start + i}", predicate=p.predicate, plain=p.plain)
            for i, p in enumerate(proposals)
        ]

    def _basis(self, conditions: list[Condition]) -> Basis:
        self._bases += 1
        return Basis(id=f"B-{self._bases}", conditions=[c.id for c in conditions])

    def _emit(self, kind: str, producer: Producer, **fields: Any) -> LedgerEvent:
        return self.ledger.append(kind, producer, **fields)
