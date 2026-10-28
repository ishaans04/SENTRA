"""PS-001 — restricted data reaches external egress through unregistered state.

The shape of the risk
---------------------
Every hop below is, on its own, an action its actor is permitted to take::

    Fictional CRM        <--read--   Support Agent      # allowed: support reads the CRM
    Support Agent        --write-->  Shared Scratchpad  # a scratchpad is just a scratchpad
    Shared Scratchpad    <--read--   Reporting Agent    # reporting reads what it is given
    Reporting Agent      --send-->   External Webhook   # reporting is allowed to report

No single-agent policy is violated. The *population* still gains a capability
nobody granted it: restricted customer data can now leave the estate.

Why this is not plain reachability
----------------------------------
The graph stores ``actor --action--> resource``. Data does not flow along those
arrows — it flows *through actors*, against the arrow on a read and with it on a
write. Naive ``has_path`` on the observed graph therefore finds nothing. PS-001
instead composes the flow explicitly: an actor that ingests from a restricted
source and deposits into an unregistered bridge, followed by an actor that
ingests from that same bridge and transmits to an external sink.

What the rule does not claim
----------------------------
It does not claim data actually left, that anyone intended it to, or that any
agent is malicious. It claims a path exists that the declared architecture
forbids, and it names the evidence.
"""

from __future__ import annotations

from hive_core.detection.base import (
    DEPOSIT_ACTIONS,
    EGRESS_ACTIONS,
    INGEST_ACTIONS,
    emergence_score,
    severity_for,
)
from hive_core.domain.models import Finding, ObservedEdge, PathStep, RiskFactor
from hive_core.graph.projection import GraphProjection

_POLICY_BASIS = (
    "No path may connect restricted data to an external destination through "
    "shared state that is absent from the declared architecture."
)


class PS001Detector:
    """Detect restricted-to-egress capability composition via unregistered state."""

    rule_id = "PS-001"

    def detect(self, projection: GraphProjection) -> list[Finding]:
        manifest = projection.manifest

        restricted_sources = set(projection.nodes_where(data_classification="restricted"))
        bridges = set(projection.nodes_where(registration="unregistered"))
        external_sinks = set(projection.nodes_where(trust="external"))

        if not (restricted_sources and bridges and external_sinks):
            return []

        # Deterministic iteration: the same graph must always yield the same
        # finding, including which path is reported when several qualify.
        for bridge in sorted(bridges):
            deposits = sorted(
                projection.edges_into(bridge, DEPOSIT_ACTIONS),
                key=lambda e: (e.first_seen, e.key),
            )
            withdrawals = sorted(
                projection.edges_into(bridge, INGEST_ACTIONS),
                key=lambda e: (e.first_seen, e.key),
            )
            if not deposits or not withdrawals:
                continue

            for deposit in deposits:
                ingest = self._ingest_of_restricted(projection, deposit.source, restricted_sources)
                if ingest is None:
                    continue

                for withdrawal in withdrawals:
                    egress = self._egress_to_external(projection, withdrawal.source, external_sinks)
                    if egress is None:
                        continue

                    return [
                        self._build_finding(
                            manifest_version=manifest.version,
                            ingest=ingest,
                            deposit=deposit,
                            withdrawal=withdrawal,
                            egress=egress,
                        )
                    ]

        return []

    # ------------------------------------------------------------------
    # Path construction
    # ------------------------------------------------------------------

    def _ingest_of_restricted(
        self,
        projection: GraphProjection,
        actor: str,
        restricted_sources: set[str],
    ) -> ObservedEdge | None:
        """The earliest restricted-source read performed by *actor*."""
        reads = [
            edge
            for edge in projection.edges_from(actor, INGEST_ACTIONS)
            if edge.target in restricted_sources
        ]
        return min(reads, key=lambda e: (e.first_seen, e.key)) if reads else None

    def _egress_to_external(
        self,
        projection: GraphProjection,
        actor: str,
        external_sinks: set[str],
    ) -> ObservedEdge | None:
        """The earliest external transmission performed by *actor*."""
        sends = [
            edge
            for edge in projection.edges_from(actor, EGRESS_ACTIONS)
            if edge.target in external_sinks
        ]
        return min(sends, key=lambda e: (e.first_seen, e.key)) if sends else None

    def _build_finding(
        self,
        *,
        manifest_version: str,
        ingest: ObservedEdge,
        deposit: ObservedEdge,
        withdrawal: ObservedEdge,
        egress: ObservedEdge,
    ) -> Finding:
        hops = [
            (ingest, "ingest: restricted data enters the population"),
            (deposit, "bridge write: data lands in unregistered shared state"),
            (withdrawal, "bridge read: a second actor picks the data up"),
            (egress, "egress: the data leaves for an external destination"),
        ]

        path = [
            PathStep(
                source=edge.source,
                action=edge.action,
                target=edge.target,
                role=role,
                expected_status=edge.expected_status,
                evidence_event_ids=list(edge.evidence_event_ids),
            )
            for edge, role in hops
        ]

        cross_agent = deposit.source != withdrawal.source
        unexpected_hops = [step for step in path if step.expected_status == "unexpected"]

        factors = [
            RiskFactor(
                id="unregistered_bridge",
                label="Unregistered shared state on the path",
                present=True,
                weight=0.25,
                detail=(
                    f"{deposit.target} carries data between actors but is not "
                    "declared in the architecture manifest."
                ),
            ),
            RiskFactor(
                id="restricted_source_reachable",
                label="Restricted data enters the path",
                present=True,
                weight=0.25,
                detail=f"{ingest.source} reads {ingest.target}, classified restricted.",
            ),
            RiskFactor(
                id="external_egress_reachable",
                label="Path terminates outside the estate",
                present=True,
                weight=0.20,
                detail=f"{egress.source} transmits to {egress.target}, an external destination.",
            ),
            RiskFactor(
                id="cross_agent_composition",
                label="Capability is composed across two different actors",
                present=cross_agent,
                weight=0.15,
                detail=(
                    f"{deposit.source} deposits and {withdrawal.source} withdraws; "
                    "neither actor holds the end-to-end capability alone."
                    if cross_agent
                    else f"{deposit.source} both deposits and withdraws."
                ),
            ),
            RiskFactor(
                id="undeclared_relationship",
                label="At least one hop is absent from the manifest",
                present=bool(unexpected_hops),
                weight=0.15,
                detail=(
                    ", ".join(f"{s.source} --{s.action}--> {s.target}" for s in unexpected_hops)
                    or "every hop is a declared relationship"
                ),
            ),
        ]

        score = emergence_score(factors)
        edges = [ingest, deposit, withdrawal, egress]

        evidence: list[str] = []
        for edge in edges:
            for event_id in edge.evidence_event_ids:
                if event_id not in evidence:
                    evidence.append(event_id)

        explanation = (
            f"{deposit.source} reads {ingest.target}, which holds restricted data, and "
            f"writes to {deposit.target} — shared state that is not part of the declared "
            f"architecture. {withdrawal.source} reads from that same resource and sends to "
            f"{egress.target}, outside the estate. Each action is individually permitted; "
            f"together they compose a route from restricted data to external egress that "
            f"no single agent was granted and the architecture does not allow."
        )

        return Finding(
            id="finding-ps001",
            rule_id="PS-001",
            title="Restricted data can reach external egress via unregistered shared state",
            status="open",
            severity=severity_for(score),
            manifest_version=manifest_version,
            detected_at_sequence=0,
            risk_factors=factors,
            emergence_score=score,
            policy_basis=_POLICY_BASIS,
            incident_node_ids=[
                ingest.target,
                deposit.source,
                deposit.target,
                withdrawal.source,
                egress.target,
            ],
            incident_edge_ids=[edge.key for edge in edges],
            incident_path=path,
            evidence_event_ids=evidence,
            explanation=explanation,
            uncertainty=(
                "HIVE observes reported interactions, not payloads. This finding "
                "establishes that the path exists, not that restricted data "
                "traversed it or that any actor intended it to."
            ),
        )
