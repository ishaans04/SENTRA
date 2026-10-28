"""Manifest loading and invariant evaluation.

An invariant is a structural property the architecture must never exhibit,
written by an operator in the manifest. Detection rules explain *how* a specific
risk arose; invariants answer the blunter question of *whether* the estate is
currently in a state its owner declared unacceptable.

The two are deliberately independent. A rule can be wrong or incomplete without
the invariant check being wrong, and the console shows both.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import yaml

from hive_core.domain.models import ArchitectureManifest, Invariant
from hive_core.graph.projection import GraphProjection


class ManifestError(ValueError):
    """Raised when a manifest cannot be loaded or is internally inconsistent."""


class PolicyEngine:
    """Load architecture manifests and evaluate their invariants."""

    def load_manifest(self, path: str | Path) -> ArchitectureManifest:
        """Read and validate the manifest at *path*."""
        manifest_path = Path(path)
        if not manifest_path.exists():
            raise ManifestError(f"No manifest at {manifest_path}")

        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ManifestError(f"{manifest_path} does not contain a mapping.")

        manifest = ArchitectureManifest(**data)
        self._check_consistency(manifest, manifest_path)
        return manifest

    def _check_consistency(self, manifest: ArchitectureManifest, source: Path) -> None:
        """Reject a manifest that references nodes it does not declare.

        A control capability pointing at a node that does not exist would look
        viable in planning and do nothing when applied, so this is caught at
        load time rather than at containment time.
        """
        declared = {node.id for node in manifest.nodes}

        for relationship in manifest.allowed_relationships:
            for node_id in (relationship.source, relationship.target):
                if node_id not in declared:
                    raise ManifestError(
                        f"{source.name}: allowed_relationships references undeclared "
                        f"node {node_id!r}."
                    )

        for capability in manifest.control_capabilities:
            referenced = [capability.target]
            if capability.source is not None:
                referenced.append(capability.source)
            for node_id in referenced:
                if node_id not in declared:
                    raise ManifestError(
                        f"{source.name}: control capability {capability.id!r} references "
                        f"undeclared node {node_id!r}."
                    )
            if capability.type == "block_edge" and (
                capability.source is None or capability.action is None
            ):
                raise ManifestError(
                    f"{source.name}: block_edge capability {capability.id!r} must declare "
                    "both 'source' and 'action'."
                )

        for zone in {node.zone for node in manifest.nodes}:
            if zone not in manifest.zones:
                raise ManifestError(
                    f"{source.name}: node zone {zone!r} has no entry under 'zones'."
                )

    # ------------------------------------------------------------------
    # Invariant evaluation
    # ------------------------------------------------------------------

    def check_invariants(self, projection: GraphProjection) -> list[dict[str, object]]:
        """Evaluate every manifest invariant against the current projection.

        An invariant is violated when a directed path runs from a node of the
        named data classification, through a bridge with the named registration
        status, to a node in the named sink zone.
        """
        manifest = projection.manifest
        results: list[dict[str, object]] = []

        for invariant in manifest.invariants:
            witness = self._find_witness(projection, invariant)
            results.append(
                {
                    "invariant": invariant.model_dump(),
                    "violated": witness is not None,
                    "witness_path": witness or [],
                }
            )
        return results

    def violations(self, projection: GraphProjection) -> list[Invariant]:
        """Only the invariants the current projection violates."""
        return [
            Invariant(**result["invariant"])  # type: ignore[arg-type]
            for result in self.check_invariants(projection)
            if result["violated"]
        ]

    def _find_witness(
        self,
        projection: GraphProjection,
        invariant: Invariant,
    ) -> list[str] | None:
        """Return one concrete source-bridge-sink path, or ``None``.

        Reachability is evaluated on the data-flow orientation of the graph, not
        the interaction orientation: an invariant asks where content can travel,
        and reads carry content against the recorded arrow.

        Returning the witness rather than a bare boolean lets the console show
        *why* an invariant is reported violated.
        """
        if invariant.status != "prohibited":
            return None

        flow = projection.data_flow_graph()

        sources = sorted(projection.nodes_where(data_classification=invariant.source_data_class))
        bridges = sorted(
            projection.nodes_where(registration=invariant.required_bridge_registration)
        )
        sinks = sorted(projection.nodes_where(zone=invariant.sink_zone))

        def reaches(start: str, end: str) -> bool:
            return flow.has_node(start) and flow.has_node(end) and nx.has_path(flow, start, end)

        for source in sources:
            for bridge in bridges:
                if source == bridge or not reaches(source, bridge):
                    continue
                for sink in sinks:
                    if bridge == sink or not reaches(bridge, sink):
                        continue
                    head = nx.shortest_path(flow, source, bridge)
                    tail = nx.shortest_path(flow, bridge, sink)
                    return list(head) + list(tail)[1:]
        return None
