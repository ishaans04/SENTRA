"""Typed condition predicates, evaluated over the engine's graph and the session ledger.

A condition is the machine-checkable part of an approval: "only reads from the
approved store" becomes ``ReadsOnlyFrom(actor, resources)``. Each predicate is a
few lines of graph or ledger query and answers with one of three results:

``HOLDS``    the evidence supports the condition
``FAILS``    the evidence contradicts it, and the witnesses say which events
``UNKNOWN``  the evidence needed to decide is missing

The model may only fill in parameters, from names in the session's manifest.
It never evaluates anything (INV-2). Semantics follow PRD §11.5. Run-scoped
conditions look only at the decision's current-epoch runs, so a run that was
renewed is not judged by what its predecessor did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from sentra.engine_bridge import EngineBridge
from sentra.ledger import LedgerEvent

Result = Literal["HOLDS", "FAILS", "UNKNOWN"]


@dataclass(frozen=True)
class ConditionContext:
    events: list[LedgerEvent]
    bridge: EngineBridge
    decision_id: str
    epoch: int


@dataclass(frozen=True)
class Evaluation:
    result: Result
    witnesses: list[str]


class _Predicate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadsOnlyFrom(_Predicate):
    kind: Literal["ReadsOnlyFrom"] = "ReadsOnlyFrom"
    actor: str
    resources: list[str]

    def describe(self) -> str:
        return f"{self.actor} only reads from {', '.join(self.resources)}"

    def evaluate(self, ctx: ConditionContext) -> Evaluation:
        reads = [
            e
            for e in ctx.events
            if e.kind == "gateway.call"
            and e.actor == self.actor
            and e.decision_id == ctx.decision_id
            and e.epoch == ctx.epoch
            and e.payload.get("effect") == "read"
            and e.payload.get("outcome") == "executed"
        ]
        observed = {o.event_id for o in ctx.bridge.observations()}
        if any(e.event_id not in observed for e in reads):
            return Evaluation("UNKNOWN", [e.event_id for e in reads if e.event_id not in observed])
        outside = [e.event_id for e in reads if e.payload.get("resource") not in self.resources]
        if outside:
            return Evaluation("FAILS", outside)
        return Evaluation("HOLDS", [e.event_id for e in reads])


class NoUndeclaredPath(_Predicate):
    kind: Literal["NoUndeclaredPath"] = "NoUndeclaredPath"
    source: str
    sink: str

    def describe(self) -> str:
        return f"no undeclared route from {self.source} to {self.sink}"

    def evaluate(self, ctx: ConditionContext) -> Evaluation:
        flow = ctx.bridge.projection.data_flow_graph()
        if self.source not in flow or flow.out_degree(self.source) == 0:
            return Evaluation("UNKNOWN", [])
        for u, v, data in flow.edges(data=True):
            if data.get("expected_status") != "unexpected":
                continue
            if not (nx.has_path(flow, self.source, u) and nx.has_path(flow, v, self.sink)):
                continue
            nodes = nx.shortest_path(flow, self.source, u) + nx.shortest_path(flow, v, self.sink)
            witnesses: list[str] = []
            for a, b in zip(nodes, nodes[1:], strict=False):
                first = next(iter(flow.get_edge_data(a, b).values()))
                witnesses.extend(first.get("evidence_event_ids", []))
            return Evaluation("FAILS", witnesses)
        return Evaluation("HOLDS", [])


class ManifestUnchanged(_Predicate):
    kind: Literal["ManifestUnchanged"] = "ManifestUnchanged"
    actor: str

    def describe(self) -> str:
        return f"{self.actor} uses only what the manifest declares"

    def evaluate(self, ctx: ConditionContext) -> Evaluation:
        if not any(node.id == self.actor for node in ctx.bridge.manifest.nodes):
            return Evaluation("UNKNOWN", [])
        undeclared = [
            event_id
            for edge in ctx.bridge.projection.edges
            if edge.source == self.actor and edge.expected_status == "unexpected"
            for event_id in edge.evidence_event_ids
        ]
        if undeclared:
            return Evaluation("FAILS", undeclared)
        return Evaluation("HOLDS", [])


Predicate = Annotated[
    ReadsOnlyFrom | NoUndeclaredPath | ManifestUnchanged, Field(discriminator="kind")
]
