"""Swarm Lab: ask what a population would do before deploying it.

The console's replay view answers "what happened?" for one recorded estate. The
lab answers a different question: *given a population of this size, with these
permissions and this much shared state, does a dangerous composition become
available at all?*

What makes the answer worth anything is that the lab does not score topologies
with a formula. It synthesises a real architecture manifest, generates a real
observation stream, folds it through the same :class:`GraphProjection`, and runs
the same :class:`PS001Detector`, :class:`PS002Detector` and
:class:`ContainmentPlanner` the live console uses. A finding here is produced by
exactly the code that would produce it in production.

Every run is seeded from a hash of its own configuration, so the same settings
always yield the same population, the same findings, and the same recommended
containment.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Literal

from hive_core.containment.planner import ContainmentPlanner
from hive_core.detection.base import Detector
from hive_core.detection.ps001 import PS001Detector
from hive_core.detection.ps002 import PS002Detector
from hive_core.domain.models import (
    ArchitectureManifest,
    ControlCapability,
    Finding,
    Node,
    ObservationEvent,
    Relationship,
)
from hive_core.graph.projection import GraphProjection

Connectivity = Literal["restricted", "normal", "open"]
SharedMemory = Literal["off", "limited", "enabled"]
Delegation = Literal["restricted", "normal", "recursive"]
ExternalAccess = Literal["none", "limited", "broad"]
Perturbation = Literal[
    "none",
    "unregistered_shared_resource",
    "cross_agent_execution",
    "delegation_cascade",
    "new_external_endpoint",
]

#: Probability that any given agent forms an extra cross-zone relationship.
_CONNECTIVITY_P: dict[str, float] = {"restricted": 0.05, "normal": 0.18, "open": 0.4}

#: Fraction of the population that touches unregistered shared state, when any
#: exists at all.
_SHARED_MEMORY_REACH: dict[str, float] = {"off": 0.0, "limited": 0.12, "enabled": 0.35}

#: Fraction of the population holding an external transmission capability.
_EXTERNAL_REACH: dict[str, float] = {"none": 0.0, "limited": 0.08, "broad": 0.3}

#: How deep delegation chains are allowed to run.
_DELEGATION_DEPTH: dict[str, int] = {"restricted": 0, "normal": 1, "recursive": 3}

_ZONES: dict[str, dict[str, Any]] = {
    "operations": {"label": "Operations", "trust": "internal"},
    "analysis": {"label": "Analysis", "trust": "internal"},
    "delivery": {"label": "Delivery", "trust": "internal"},
    "approved-state": {"label": "Approved state", "trust": "internal"},
    "shared-state": {"label": "Shared state", "trust": "untrusted"},
    "external": {"label": "External", "trust": "external"},
}

_AGENT_ZONES = ("operations", "analysis", "delivery")

_RESTRICTED_SOURCE = "Synthetic Records Store"
_APPROVED_STORE = "Synthetic Approved Store"
_SHARED_RESOURCE = "Unregistered Shared Buffer"
_EXTERNAL_SINK = "Simulated External Endpoint"


@dataclass(frozen=True)
class SwarmConfig:
    """One lab experiment. Fully determines the outcome."""

    population: int = 24
    connectivity: Connectivity = "normal"
    shared_memory: SharedMemory = "limited"
    delegation: Delegation = "normal"
    external_access: ExternalAccess = "limited"
    perturbation: Perturbation = "unregistered_shared_resource"

    def seed(self) -> int:
        """A stable seed derived from the configuration itself."""
        material = "|".join(
            str(value)
            for value in (
                self.population,
                self.connectivity,
                self.shared_memory,
                self.delegation,
                self.external_access,
                self.perturbation,
            )
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return int(digest[:16], 16)


class SwarmSimulator:
    """Synthesise a population, observe it, and run the real analysis on it."""

    #: Bounds keep a lab run cheap enough to stay interactive.
    MIN_POPULATION = 3
    MAX_POPULATION = 200

    def run(self, config: SwarmConfig) -> dict[str, Any]:
        """Execute one experiment and return its full result."""
        population = max(self.MIN_POPULATION, min(self.MAX_POPULATION, config.population))
        config = SwarmConfig(
            population=population,
            connectivity=config.connectivity,
            shared_memory=config.shared_memory,
            delegation=config.delegation,
            external_access=config.external_access,
            perturbation=config.perturbation,
        )

        rng = random.Random(config.seed())
        manifest = self._build_manifest(config)
        events = self._generate_events(config, manifest, rng)

        projection = GraphProjection(manifest)
        projection.apply_events(events)

        detectors: list[Detector] = [PS001Detector(), PS002Detector()]
        findings: list[Finding] = [
            finding for detector in detectors for finding in detector.detect(projection)
        ]

        planner = ContainmentPlanner(manifest, detectors)
        plans = [planner.plan(finding, projection) for finding in findings]

        return {
            "config": {
                "population": config.population,
                "connectivity": config.connectivity,
                "shared_memory": config.shared_memory,
                "delegation": config.delegation,
                "external_access": config.external_access,
                "perturbation": config.perturbation,
            },
            "outcome": "risk_detected" if findings else "no_composition_found",
            "population": {
                "agents": sum(1 for node in manifest.nodes if node.kind == "agent"),
                "resources": sum(1 for node in manifest.nodes if node.kind != "agent"),
                "observations": len(events),
                "relationships": len(projection.edges),
                "undeclared_relationships": sum(
                    1 for edge in projection.edges if edge.expected_status == "unexpected"
                ),
            },
            "findings": [finding.model_dump() for finding in findings],
            "plans": [plan.model_dump() for plan in plans],
            "interpretation": self._interpret(config, findings, plans),
            "determinism": {
                "seed": config.seed(),
                "note": "The same configuration always produces this exact result.",
            },
        }

    # ------------------------------------------------------------------
    # Population synthesis
    # ------------------------------------------------------------------

    def _build_manifest(self, config: SwarmConfig) -> ArchitectureManifest:
        """Declare the architecture this synthetic population is meant to follow."""
        nodes: list[Node] = [
            Node(
                id=_RESTRICTED_SOURCE,
                kind="datasource",
                label=_RESTRICTED_SOURCE,
                zone="operations",
                data_classification="restricted",
                registration="expected",
            ),
            Node(
                id=_APPROVED_STORE,
                kind="store",
                label=_APPROVED_STORE,
                zone="approved-state",
                data_classification="internal",
                registration="expected",
            ),
            Node(
                id=_EXTERNAL_SINK,
                kind="destination",
                label=_EXTERNAL_SINK,
                zone="external",
                data_classification="public",
                registration="expected",
            ),
        ]

        agents = [f"Agent {index:03d}" for index in range(1, config.population + 1)]
        for index, agent in enumerate(agents):
            nodes.append(
                Node(
                    id=agent,
                    kind="agent",
                    label=agent,
                    zone=_AGENT_ZONES[index % len(_AGENT_ZONES)],
                    data_classification="internal",
                    registration="expected",
                )
            )

        if self._shared_resource_present(config):
            nodes.append(
                Node(
                    id=_SHARED_RESOURCE,
                    kind="store",
                    label=_SHARED_RESOURCE,
                    zone="shared-state",
                    data_classification="internal",
                    registration="unregistered",
                )
            )

        # Declared relationships: reading records, filing to approved storage,
        # and — for the agents that hold it — transmitting outward. All of this
        # is sanctioned. None of it is the risk.
        allowed: list[Relationship] = []
        for agent in agents:
            allowed.append(Relationship(source=agent, action="read", target=_RESTRICTED_SOURCE))
            allowed.append(Relationship(source=agent, action="write", target=_APPROVED_STORE))
            allowed.append(Relationship(source=agent, action="read", target=_APPROVED_STORE))
        for agent in self._egress_holders(config, agents):
            allowed.append(Relationship(source=agent, action="send", target=_EXTERNAL_SINK))
        if config.perturbation == "cross_agent_execution":
            for agent in agents:
                allowed.append(Relationship(source=agent, action="execute", target=_APPROVED_STORE))

        capabilities = self._build_capabilities(config, agents)

        return ArchitectureManifest(
            version=f"synthetic/{config.seed():x}",
            zones=_ZONES,
            nodes=nodes,
            allowed_relationships=allowed,
            invariants=[],
            control_capabilities=capabilities,
        )

    def _build_capabilities(
        self, config: SwarmConfig, agents: list[str]
    ) -> list[ControlCapability]:
        """Register the controls an operator would plausibly pre-authorise."""
        if not self._shared_resource_present(config):
            return []

        capabilities: list[ControlCapability] = [
            ControlCapability(
                id="quarantine-shared-buffer",
                type="quarantine_node",
                label=f"Quarantine {_SHARED_RESOURCE}",
                target=_SHARED_RESOURCE,
                reversible=True,
                cost=len(self._shared_memory_users(config, agents)) or 1,
                rationale="Isolates the undeclared resource from the whole population.",
            )
        ]
        # A targeted control per depositing agent, so the planner has a genuinely
        # cheaper option than isolating the resource outright.
        for agent in self._shared_memory_users(config, agents):
            capabilities.append(
                ControlCapability(
                    id=f"block-{agent.replace(' ', '-').lower()}-buffer-write",
                    type="block_edge",
                    label=f"Block {agent} writes to {_SHARED_RESOURCE}",
                    source=agent,
                    action="write",
                    target=_SHARED_RESOURCE,
                    reversible=True,
                    cost=1,
                    rationale="Severs one deposit relationship without touching anything else.",
                )
            )
        return capabilities

    # ------------------------------------------------------------------
    # Observation synthesis
    # ------------------------------------------------------------------

    def _generate_events(
        self,
        config: SwarmConfig,
        manifest: ArchitectureManifest,
        rng: random.Random,
    ) -> list[ObservationEvent]:
        """Produce the observation stream this population would emit."""
        agents = [node.id for node in manifest.nodes if node.kind == "agent"]
        events: list[ObservationEvent] = []
        sequence = 0

        def emit(actor: str, action: str, target: str, **context: Any) -> None:
            nonlocal sequence
            sequence += 1
            events.append(
                ObservationEvent(
                    event_id=f"swarm-{sequence:05d}",
                    sequence=sequence,
                    occurred_at=f"2026-09-19T12:00:{sequence % 60:02d}Z",
                    actor=actor,
                    action=action,  # type: ignore[arg-type]
                    target=target,
                    context={"synthetic": True, **context},
                    provenance={"source": "swarm-lab"},
                    result="success",
                )
            )

        # Baseline: everyone does declared work.
        readers = self._record_readers(agents)
        for agent in readers:
            emit(agent, "read", _RESTRICTED_SOURCE, phase="baseline")
        for agent in agents:
            emit(agent, "write", _APPROVED_STORE, phase="baseline")

        egress_holders = self._egress_holders(config, agents)
        for agent in egress_holders:
            emit(agent, "send", _EXTERNAL_SINK, phase="baseline")

        # Delegation chains: modelled but not themselves a finding. They widen
        # who can reach what, which is what makes them worth configuring.
        depth = _DELEGATION_DEPTH[config.delegation]
        for _ in range(depth):
            for agent in rng.sample(agents, k=max(1, len(agents) // 6)):
                peer = rng.choice([a for a in agents if a != agent])
                emit(agent, "delegate", peer, phase="baseline")

        # Perturbation: the structural change under test.
        if self._shared_resource_present(config):
            users = self._shared_memory_users(config, agents)
            # Whoever holds the sensitive input deposits; whoever holds the
            # onward capability withdraws. That split is what decides whether a
            # composition can close, so it is derived rather than random.
            depositors = [a for a in users if a in readers] or users[: max(1, len(users) // 2)]
            withdrawers = [a for a in users if a in egress_holders]
            if not withdrawers:
                withdrawers = [a for a in users if a not in depositors] or users[-1:]

            for agent in depositors:
                emit(agent, "discover", _SHARED_RESOURCE, phase="perturbation")
                emit(agent, "write", _SHARED_RESOURCE, phase="perturbation")

            if config.perturbation == "cross_agent_execution":
                for agent in withdrawers:
                    emit(agent, "discover", _SHARED_RESOURCE, phase="perturbation")
                    emit(agent, "execute", _SHARED_RESOURCE, phase="perturbation")
            else:
                for agent in withdrawers:
                    emit(agent, "discover", _SHARED_RESOURCE, phase="perturbation")
                    emit(agent, "read", _SHARED_RESOURCE, phase="perturbation")

        if config.perturbation == "new_external_endpoint":
            # Egress appears for agents that were never granted it.
            newly_external = [a for a in agents if a not in egress_holders]
            for agent in (
                rng.sample(newly_external, k=min(len(newly_external), 3)) if newly_external else []
            ):
                emit(agent, "send", _EXTERNAL_SINK, phase="perturbation")

        # Incidental cross-zone chatter, scaled by the connectivity setting.
        p_edge = _CONNECTIVITY_P[config.connectivity]
        for agent in agents:
            if rng.random() < p_edge:
                emit(agent, "read", _APPROVED_STORE, phase="background")

        return events

    # ------------------------------------------------------------------
    # Cohort selection (deterministic given the seeded rng)
    # ------------------------------------------------------------------

    def _shared_resource_present(self, config: SwarmConfig) -> bool:
        if config.perturbation in ("unregistered_shared_resource", "cross_agent_execution"):
            return config.shared_memory != "off"
        return False

    def _shared_memory_users(self, config: SwarmConfig, agents: list[str]) -> list[str]:
        """Agents that touch the undeclared resource.

        The cohort is drawn from both ends of the population rather than a
        contiguous block. Agents that read the restricted source sit at the front
        and agents holding external capability sit at the back, so a contiguous
        slice would never contain both — and the lab would report "no risk" for a
        structural reason that has nothing to do with the configuration under
        test.
        """
        reach = _SHARED_MEMORY_REACH[config.shared_memory]
        if not reach:
            return []
        count = min(max(2, round(len(agents) * reach)), len(agents))
        head = (count + 1) // 2
        tail = count - head
        selected = agents[:head] + (agents[-tail:] if tail else [])
        # Preserve population order and drop any overlap from a small population.
        return [agent for agent in agents if agent in set(selected)]

    def _egress_holders(self, config: SwarmConfig, agents: list[str]) -> list[str]:
        reach = _EXTERNAL_REACH[config.external_access]
        count = max(1, round(len(agents) * reach)) if reach else 0
        return agents[-count:] if count else []

    def _record_readers(self, agents: list[str]) -> list[str]:
        """Agents that actually touch the restricted source during the run."""
        return agents[: max(1, len(agents) // 2)]

    # ------------------------------------------------------------------
    # Narration
    # ------------------------------------------------------------------

    def _interpret(self, config: SwarmConfig, findings: list[Any], plans: list[Any]) -> str:
        if not findings:
            if not self._shared_resource_present(config):
                return (
                    "No undeclared shared state exists in this configuration, so no "
                    "cross-agent composition can form. Enable shared memory, or choose "
                    "a perturbation that introduces an undeclared resource, to test "
                    "whether one would."
                )
            if config.external_access == "none" and config.perturbation != "cross_agent_execution":
                return (
                    "Agents share undeclared state, but no agent in this population "
                    "holds an external transmission capability, so the composition "
                    "has nowhere to terminate. Grant limited external access to see "
                    "the path close."
                )
            return (
                "The population formed undeclared relationships, but they do not "
                "compose into a path either rule recognises. This is the useful "
                "negative result: shared state alone is not the risk."
            )

        recommendation = next(
            (plan.recommended_capability_id for plan in plans if plan.recommended_capability_id),
            None,
        )
        rules = ", ".join(sorted({finding.rule_id for finding in findings}))
        if recommendation:
            return (
                f"This population composes a capability {rules} recognises. The same "
                f"planner the console uses evaluated every registered control and "
                f"recommends {recommendation} as the least disruptive action that "
                f"removes the path. Reconfigure and re-run to find the setting where "
                f"the composition no longer forms at all."
            )
        return (
            f"This population composes a capability {rules} recognises, and no "
            f"registered control removes it without breaking declared work. That is "
            f"a design problem, not an incident: the architecture needs a control it "
            f"does not currently have."
        )
