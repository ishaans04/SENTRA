"""PS-002 — one agent executes content another agent authored.

The shape of the risk
---------------------
Agent A writes to a shared resource. Agent B later runs what it finds there::

    Research Agent    --write-->    Shared Task Queue
    Shared Task Queue <--execute--  Build Agent

Each half looks routine. Composed, they form an indirect instruction channel:
whatever reaches Agent A's output — including content Agent A itself ingested
from an untrusted source — becomes something Agent B will run. This is the
structural precondition behind indirect prompt injection and cross-agent
tool-chaining, expressed as a property of the topology rather than of any
individual message.

The rule fires on the *shape*, not on payload inspection. HIVE never reads
content; it observes that an execute relationship consumes a resource written
by a different actor, and it reports which hop made that possible.

Escalation
----------
Severity rises when the writing actor itself ingested from outside the estate
or from a resource the architecture does not declare, because the channel then
reaches all the way from untrusted input to execution.
"""

from __future__ import annotations

from hive_core.detection.base import (
    DEPOSIT_ACTIONS,
    EXECUTE_ACTIONS,
    INGEST_ACTIONS,
    emergence_score,
    severity_for,
)
from hive_core.domain.models import Finding, ObservedEdge, PathStep, RiskFactor
from hive_core.graph.projection import GraphProjection

_POLICY_BASIS = (
    "An actor may not execute content authored by a different actor through "
    "shared state, unless that relationship is declared in the architecture."
)


class PS002Detector:
    """Detect cross-actor execution of content delivered through shared state."""

    rule_id = "PS-002"

    def detect(self, projection: GraphProjection) -> list[Finding]:
        manifest = projection.manifest

        executions = sorted(
            (edge for edge in projection.edges if edge.action in EXECUTE_ACTIONS),
            key=lambda e: (e.first_seen, e.key),
        )
        if not executions:
            return []

        for execution in executions:
            authors = sorted(
                (
                    edge
                    for edge in projection.edges_into(execution.target, DEPOSIT_ACTIONS)
                    if edge.source != execution.source
                ),
                key=lambda e: (e.first_seen, e.key),
            )
            # An operator who declared both halves of a channel has accepted it.
            # A planner reviewing work and a build agent executing approved work
            # is exactly that: cross-actor by design, and not a deviation.
            # PS-002 reports the channels the architecture never sanctioned.
            undeclared_authors = [
                author
                for author in authors
                if author.expected_status == "unexpected"
                or execution.expected_status == "unexpected"
            ]
            if not undeclared_authors:
                continue

            author_write = undeclared_authors[0]
            upstream = self._untrusted_upstream(projection, author_write.source)

            return [
                self._build_finding(
                    manifest_version=manifest.version,
                    author_write=author_write,
                    execution=execution,
                    upstream=upstream,
                )
            ]

        return []

    # ------------------------------------------------------------------
    # Path construction
    # ------------------------------------------------------------------

    def _untrusted_upstream(self, projection: GraphProjection, actor: str) -> ObservedEdge | None:
        """The earliest read *actor* performed against untrusted or external input.

        Its presence is what turns a merely unusual execution relationship into a
        complete untrusted-input-to-execution channel.
        """
        candidates = [
            edge
            for edge in projection.edges_from(actor, INGEST_ACTIONS)
            if projection.graph.nodes.get(edge.target, {}).get("trust") in ("untrusted", "external")
        ]
        return min(candidates, key=lambda e: (e.first_seen, e.key)) if candidates else None

    def _build_finding(
        self,
        *,
        manifest_version: str,
        author_write: ObservedEdge,
        execution: ObservedEdge,
        upstream: ObservedEdge | None,
    ) -> Finding:
        hops: list[tuple[ObservedEdge, str]] = []
        if upstream is not None:
            hops.append((upstream, "untrusted ingest: the author reads content it did not produce"))
        hops.append((author_write, "deposit: the author writes to shared state"))
        hops.append((execution, "execution: a different actor runs what it finds there"))

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

        undeclared_hops = [
            f"{edge.source} --{edge.action}--> {edge.target}"
            for edge in (author_write, execution)
            if edge.expected_status == "unexpected"
        ]

        factors = [
            RiskFactor(
                id="cross_actor_execution",
                label="Executed content was authored by a different actor",
                present=True,
                weight=0.25,
                detail=(
                    f"{execution.source} executes {execution.target}, which "
                    f"{author_write.source} writes to."
                ),
            ),
            RiskFactor(
                id="undeclared_channel",
                label="The channel is absent from the declared architecture",
                present=bool(undeclared_hops),
                weight=0.25,
                detail=(
                    "Undeclared hops: " + "; ".join(undeclared_hops)
                    if undeclared_hops
                    else "Both halves of the channel are declared."
                ),
            ),
            RiskFactor(
                id="shared_state_channel",
                label="The channel runs through shared state, not a direct call",
                present=True,
                weight=0.15,
                detail=(
                    f"{execution.target} decouples author from executor, so neither "
                    "side sees the full relationship."
                ),
            ),
            RiskFactor(
                id="untrusted_upstream",
                label="The author ingested from an untrusted or external source",
                present=upstream is not None,
                weight=0.35,
                detail=(
                    f"{upstream.source} reads {upstream.target} before writing, "
                    "completing an untrusted-input-to-execution channel."
                    if upstream is not None
                    else "No untrusted upstream read was observed for the author."
                ),
            ),
        ]

        score = emergence_score(factors)
        edges = [edge for edge, _ in hops]

        evidence: list[str] = []
        for edge in edges:
            for event_id in edge.evidence_event_ids:
                if event_id not in evidence:
                    evidence.append(event_id)

        explanation = (
            f"{execution.source} executes content from {execution.target}, a resource "
            f"written by {author_write.source}. The two actors never interact directly, "
            f"so neither one's permissions describe the relationship between them. "
            + (
                f"{upstream.source} first read {upstream.target}, which sits outside "
                f"the trusted estate — the channel therefore reaches from untrusted "
                f"input all the way to execution."
                if upstream is not None
                else "No untrusted upstream source was observed, so the channel is "
                "currently internal."
            )
        )

        node_ids = [author_write.source, execution.target, execution.source]
        if upstream is not None:
            node_ids.insert(0, upstream.target)

        return Finding(
            id="finding-ps002",
            rule_id="PS-002",
            title="One actor executes content authored by another through shared state",
            status="open",
            severity=severity_for(score),
            manifest_version=manifest_version,
            detected_at_sequence=0,
            risk_factors=factors,
            emergence_score=score,
            policy_basis=_POLICY_BASIS,
            incident_node_ids=node_ids,
            incident_edge_ids=[edge.key for edge in edges],
            incident_path=path,
            evidence_event_ids=evidence,
            explanation=explanation,
            uncertainty=(
                "HIVE does not inspect payloads. This finding establishes that an "
                "indirect instruction channel exists between two actors, not that "
                "hostile content has travelled along it."
            ),
        )
