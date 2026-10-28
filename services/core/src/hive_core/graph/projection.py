"""Temporal projection of the observation ledger into an interaction graph.

Why a multigraph
----------------
Two agents can relate through more than one action at once: the Support Agent
both ``discover``s and ``write``s to the same scratchpad. A simple directed
graph keeps only one edge per node pair, so the second action silently
overwrites the first and a containment action scoped to ``write`` becomes
impossible to model faithfully.

``networkx.MultiDiGraph`` keyed by action fixes that: ``(u, v, action)`` is the
unit of the graph, exactly as ``(actor, action, target)`` is the unit of an
observation. That equivalence is what lets the containment planner simulate a
control and then apply the *same* control for real, with no divergence.

Rebuildability
--------------
The graph is a derived view. The ledger is the evidence. ``reset()`` plus a
replay of the same events always reproduces an identical projection, which is
what makes every finding reproducible.
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from hive_core.domain.models import (
    ArchitectureManifest,
    ObservationEvent,
    ObservedEdge,
)

#: Actions that carry a control instruction rather than an observation.
_CONTROL_ACTIONS = frozenset({"block"})


class GraphProjection:
    """An append-only projection of observations onto a typed interaction graph."""

    def __init__(self, manifest: ArchitectureManifest) -> None:
        self.manifest = manifest
        self.graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
        #: ``(source, target, action)`` -> edge record. The canonical edge set;
        #: the networkx graph is kept in lockstep with it.
        self._edges: dict[tuple[str, str, str], ObservedEdge] = {}
        #: Capability ids whose block event has been applied, for introspection.
        self.applied_controls: list[str] = []
        self._seed_expected_nodes()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _seed_expected_nodes(self) -> None:
        """Place every declared node on the graph before any event arrives.

        Seeding up front means the baseline view shows the architecture the
        operator declared, including parts of it that have not acted yet.
        """
        for node in self.manifest.nodes:
            self.graph.add_node(
                node.id,
                **node.model_dump(),
                trust=self.manifest.zone_trust(node.zone),
                declared=True,
            )

    # ------------------------------------------------------------------
    # Event application
    # ------------------------------------------------------------------

    def apply_events(self, events: list[ObservationEvent]) -> None:
        """Fold *events* into the projection, in the order given.

        Applying the same event twice is a no-op beyond refreshing ``last_seen``
        and the observation count, so replay is safe to restart at any point.
        """
        for event in events:
            if event.action in _CONTROL_ACTIONS:
                self._apply_control(event)
            else:
                self._apply_observation(event)

    def _apply_observation(self, event: ObservationEvent) -> None:
        self._ensure_node(event.actor, event.context.get("source_zone"))
        self._ensure_node(event.target, event.context.get("target_zone"))

        key = (event.actor, event.target, event.action)
        existing = self._edges.get(key)

        if existing is not None:
            existing.last_seen = event.occurred_at
            if event.event_id not in existing.evidence_event_ids:
                existing.evidence_event_ids.append(event.event_id)
                existing.observation_count += 1
            edge = existing
        else:
            edge = ObservedEdge(
                source=event.actor,
                target=event.target,
                action=event.action,
                first_seen=event.occurred_at,
                last_seen=event.occurred_at,
                expected_status=(
                    "expected"
                    if self.manifest.allows(event.actor, event.action, event.target)
                    else "unexpected"
                ),
                observation_count=1,
                evidence_event_ids=[event.event_id],
            )
            self._edges[key] = edge

        self.graph.add_edge(event.actor, event.target, key=event.action, **edge.model_dump())

    def _apply_control(self, event: ObservationEvent) -> None:
        """Sever the relationship named by a HIVE control event.

        A ``block`` event carries the exact edge to remove in its context, so the
        effect of applying a control is identical to the effect the planner
        simulated when it chose that control.
        """
        capability_id = event.context.get("capability_id")
        control_type = event.context.get("control_type", "block_edge")

        if control_type == "quarantine_node":
            self.quarantine_node(event.target)
        else:
            source = event.context.get("source")
            action = event.context.get("blocked_action")
            if source is None or action is None:
                raise ValueError(
                    f"block_edge control event {event.event_id!r} must carry "
                    "'source' and 'blocked_action' in its context"
                )
            self.remove_edge(source, event.target, action)

        if capability_id and capability_id not in self.applied_controls:
            self.applied_controls.append(capability_id)

    # ------------------------------------------------------------------
    # Mutation primitives
    # ------------------------------------------------------------------

    def remove_edge(self, source: str, target: str, action: str) -> bool:
        """Remove exactly one ``source --action--> target`` relationship.

        Returns ``True`` when a relationship was actually present and severed.
        """
        key = (source, target, action)
        removed = self._edges.pop(key, None) is not None
        if self.graph.has_edge(source, target, key=action):
            self.graph.remove_edge(source, target, key=action)
            removed = True
        return removed

    def quarantine_node(self, node_id: str) -> int:
        """Remove every relationship incident to *node_id*, keeping the node itself.

        The node stays on the graph so the console can show what was isolated
        rather than silently erasing it from the topology.
        """
        doomed = [k for k in self._edges if k[0] == node_id or k[1] == node_id]
        for source, target, action in doomed:
            self.remove_edge(source, target, action)
        return len(doomed)

    def _ensure_node(self, node_id: str, zone_hint: str | None) -> None:
        """Add an undeclared node the ledger mentions but the manifest does not.

        An undeclared node is itself a signal, so it is marked ``declared=False``
        and its registration recorded as ``unknown`` rather than assumed benign.
        """
        if self.graph.has_node(node_id):
            return
        zone = zone_hint or "unknown"
        self.graph.add_node(
            node_id,
            id=node_id,
            kind="store",
            label=node_id,
            zone=zone,
            data_classification="internal",
            registration="unknown",
            trust=self.manifest.zone_trust(zone),
            declared=False,
        )

    def reset(self) -> None:
        """Return to the seeded baseline, discarding every observed relationship."""
        self._edges.clear()
        self.applied_controls.clear()
        self.graph.clear()
        self._seed_expected_nodes()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def edges(self) -> list[ObservedEdge]:
        """Every currently active relationship, in first-observed order."""
        return sorted(self._edges.values(), key=lambda e: (e.first_seen, e.key))

    def edges_from(self, source: str, actions: frozenset[str]) -> list[ObservedEdge]:
        """Active relationships out of *source* whose action is in *actions*."""
        return [
            edge
            for (src, _, action), edge in self._edges.items()
            if src == source and action in actions
        ]

    def edges_into(self, target: str, actions: frozenset[str]) -> list[ObservedEdge]:
        """Active relationships into *target* whose action is in *actions*."""
        return [
            edge
            for (_, tgt, action), edge in self._edges.items()
            if tgt == target and action in actions
        ]

    def edge(self, source: str, target: str, action: str) -> ObservedEdge | None:
        return self._edges.get((source, target, action))

    def nodes_where(self, **criteria: Any) -> list[str]:
        """Node ids whose attributes match every keyword criterion."""
        return [
            node_id
            for node_id, data in self.graph.nodes(data=True)
            if all(data.get(field) == value for field, value in criteria.items())
        ]

    def has_path(self, source: str, target: str) -> bool:
        """True when a directed path connects *source* to *target*."""
        if not (self.graph.has_node(source) and self.graph.has_node(target)):
            return False
        return nx.has_path(self.graph, source, target)

    def data_flow_graph(self) -> nx.MultiDiGraph[str]:
        """The interaction graph re-oriented so arrows follow the data.

        Interactions are recorded as ``actor --action--> resource``, because that
        is what a collector observes. Data does not travel that way. A read moves
        content *from* the resource *into* the actor, against the arrow; a write
        or a send moves it the way the arrow already points.

        Re-orienting reads is what turns "can restricted data reach the outside
        world?" into an ordinary reachability question. Without it, a CRM has no
        outgoing edges at all and every such query answers no.

        Discovery is omitted rather than oriented. Knowing that a resource exists
        moves no content in either direction, and including it would make a
        severed write look like an open route simply because the actor still
        remembers the address.
        """
        from hive_core.detection.base import DISCOVERY_ACTIONS, INGEST_ACTIONS

        flow: nx.MultiDiGraph[str] = nx.MultiDiGraph()
        flow.add_nodes_from(self.graph.nodes(data=True))
        for edge in self._edges.values():
            if edge.action in DISCOVERY_ACTIONS:
                continue
            if edge.action in INGEST_ACTIONS:
                flow.add_edge(edge.target, edge.source, key=edge.action, **edge.model_dump())
            else:
                flow.add_edge(edge.source, edge.target, key=edge.action, **edge.model_dump())
        return flow

    def data_reaches(self, source: str, target: str) -> bool:
        """True when content originating at *source* could reach *target*."""
        flow = self.data_flow_graph()
        if not (flow.has_node(source) and flow.has_node(target)):
            return False
        return nx.has_path(flow, source, target)

    def copy(self) -> GraphProjection:
        """A deep enough copy to run counterfactual simulations against.

        The planner mutates the copy to answer "what would this control do?"
        without touching the live projection.
        """
        clone = GraphProjection.__new__(GraphProjection)
        clone.manifest = self.manifest
        clone.graph = self.graph.copy()
        clone._edges = {k: v.model_copy(deep=True) for k, v in self._edges.items()}
        clone.applied_controls = list(self.applied_controls)
        return clone

    def snapshot(self) -> dict[str, Any]:
        """A serialisable view of the current projection for transport."""
        return {
            "nodes": [{**data, "id": node_id} for node_id, data in self.graph.nodes(data=True)],
            "edges": [{**edge.model_dump(), "id": edge.key} for edge in self.edges],
            "applied_controls": list(self.applied_controls),
        }
