"""The decision graph: decisions, conditions, evidence, runs, actions and findings.

It is a fold over the session ledger. ``apply`` takes one event and updates the
models and a NetworkX ``MultiDiGraph`` with the node and edge types of PRD §11.3.
Nothing writes to it any other way, so ``DecisionGraph.replay(events)`` over an
exported ledger rebuilds exactly the same state (INV-5).

The earned-fact rule comes from the AEGIS store, where a claim became a fact
only by acquiring a ``VERIFIED_BY`` edge. Here a piece of evidence is ``checked``
only if it is linked to the thing it measured. Evidence recorded as checked
without that link is refused, not quietly downgraded.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import networkx as nx

from aegis.decisions.models import Condition, Decision, Evidence
from aegis.ledger import LedgerEvent


class DecisionGraph:
    def __init__(self) -> None:
        self.decisions: dict[str, Decision] = {}
        self.conditions: dict[str, Condition] = {}
        self.evidence: dict[str, Evidence] = {}
        self.graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()

    @classmethod
    def replay(cls, events: Iterable[LedgerEvent]) -> DecisionGraph:
        graph = cls()
        for event in events:
            graph.apply(event)
        return graph

    def apply(self, event: LedgerEvent) -> None:
        handler = getattr(self, "_on_" + event.kind.replace(".", "_"), None)
        if handler is not None:
            handler(event)

    # -- reading --------------------------------------------------------------

    def decisions_on(self, condition_id: str) -> list[Decision]:
        return [d for d in self.decisions.values() for b in d.bases if condition_id in b.conditions]

    def dependents(self, decision_id: str) -> list[str]:
        """Everything that stands on *decision_id*: its runs and their actions."""
        found: list[str] = []
        frontier = [decision_id]
        while frontier:
            node = frontier.pop(0)
            for _, child, key in self.graph.out_edges(node, keys=True):
                if key == "AUTHORIZES" and child not in found:
                    found.append(child)
                    frontier.append(child)
            for parent, _, key in self.graph.in_edges(node, keys=True):
                if key == "DEPENDS_ON" and parent not in found and parent != decision_id:
                    found.append(parent)
        return found

    def snapshot(self) -> dict[str, Any]:
        return {
            "decisions": {k: v.model_dump() for k, v in sorted(self.decisions.items())},
            "conditions": {k: v.model_dump() for k, v in sorted(self.conditions.items())},
            "evidence": {k: v.model_dump() for k, v in sorted(self.evidence.items())},
            "edges": sorted((u, v, k) for u, v, k in self.graph.edges(keys=True)),
        }

    # -- folding --------------------------------------------------------------

    def _decision(self, event: LedgerEvent) -> Decision:
        return self.decisions[str(event.decision_id)]

    def _on_decision_proposed(self, event: LedgerEvent) -> None:
        decision = Decision(**event.payload["decision"])
        self.decisions[decision.id] = decision
        self.graph.add_node(decision.id, type="Decision")
        for raw in event.payload.get("conditions", []):
            condition = Condition(**raw)
            self.conditions[condition.id] = condition
            self.graph.add_node(condition.id, type="Condition")
            self.graph.add_edge(decision.id, condition.id, key="DEPENDS_ON")

    def _on_decision_confirmed(self, event: LedgerEvent) -> None:
        self._decision(event).status = "active"

    def _on_decision_discarded(self, event: LedgerEvent) -> None:
        self._decision(event).status = "discarded"

    def _on_decision_needs_review(self, event: LedgerEvent) -> None:
        self._decision(event).status = "needs_review"

    def _on_decision_suspended(self, event: LedgerEvent) -> None:
        decision = self._decision(event)
        decision.status = "suspended"
        decision.epoch = int(event.payload["new_epoch"])

    def _on_decision_renewed(self, event: LedgerEvent) -> None:
        decision = self._decision(event)
        decision.status = "active"
        for basis in decision.bases:
            basis.accepted = True
            for condition_id in basis.conditions:
                self.conditions[condition_id].last_result = None
                self.conditions[condition_id].witnesses = []

    def _on_decision_withdrawn(self, event: LedgerEvent) -> None:
        self._decision(event).status = "withdrawn"

    def _on_condition_evaluated(self, event: LedgerEvent) -> None:
        condition = self.conditions[event.payload["condition_id"]]
        condition.last_result = event.payload["result"]
        condition.witnesses = list(event.payload.get("witnesses", []))
        cause = event.payload.get("cause")
        if cause and condition.last_result == "FAILS":
            self.graph.add_edge(cause, condition.id, key="INVALIDATES")

    def _on_basis_withdrawn(self, event: LedgerEvent) -> None:
        for basis in self._decision(event).bases:
            if basis.id == event.payload["basis_id"]:
                basis.accepted = False

    def _on_finding_raised(self, event: LedgerEvent) -> None:
        self.graph.add_node(event.payload["id"], type="Finding")

    def _on_run_started(self, event: LedgerEvent) -> None:
        self.graph.add_node(str(event.run_id), type="Run")
        self.graph.add_edge(str(event.decision_id), str(event.run_id), key="AUTHORIZES")

    def _on_action_queued(self, event: LedgerEvent) -> None:
        action_id = event.payload["action_id"]
        self.graph.add_node(action_id, type="Action")
        self.graph.add_edge(action_id, str(event.decision_id), key="DEPENDS_ON")
        self.graph.add_edge(action_id, str(event.run_id), key="DEPENDS_ON")

    def _on_evidence_recorded(self, event: LedgerEvent) -> None:
        payload = dict(event.payload)
        verifies = payload.pop("verifies", None)
        evidence = Evidence(**payload)
        if evidence.kind == "checked" and not verifies:
            raise ValueError(
                f"Evidence {evidence.id!r} is recorded as checked but is not VERIFIED_BY-linked "
                "to what it measured."
            )
        self.evidence[evidence.id] = evidence
        self.graph.add_node(evidence.id, type="Evidence")
        if verifies:
            self.graph.add_edge(verifies, evidence.id, key="VERIFIED_BY")
