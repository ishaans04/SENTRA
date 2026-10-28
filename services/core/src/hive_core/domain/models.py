"""Typed security concepts shared by every layer of the HIVE core.

This module is deliberately pure: it imports nothing from the web, graph,
persistence, or connector layers. Every other package depends inwards on these
definitions, never the other way round.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------

#: Every action an observation may report. ``block`` is reserved for control
#: events emitted by HIVE itself and never appears in a scenario fixture.
Action = Literal[
    "read",
    "write",
    "call",
    "message",
    "delegate",
    "discover",
    "send",
    "execute",
    "block",
]

NodeKind = Literal[
    "agent",
    "store",
    "datasource",
    "tool",
    "api",
    "destination",
    "control_point",
]

DataClassification = Literal["public", "internal", "restricted"]

Registration = Literal["expected", "unregistered", "unknown"]

#: Trust posture declared for a zone. Detectors read this from the manifest
#: rather than matching fixture names, so the rules stay scenario-agnostic.
Trust = Literal["internal", "untrusted", "external"]

Severity = Literal["low", "medium", "high", "critical"]


# ---------------------------------------------------------------------------
# Architecture manifest
# ---------------------------------------------------------------------------


class Node(BaseModel):
    """A declared participant in the expected architecture."""

    id: str
    kind: NodeKind
    label: str
    zone: str
    data_classification: DataClassification
    registration: Registration


class Relationship(BaseModel):
    """An interaction the architecture explicitly permits."""

    source: str
    action: Action
    target: str


class ControlCapability(BaseModel):
    """A pre-authorised, reversible intervention HIVE is allowed to propose.

    HIVE never invents an action. The planner may only select from capabilities
    an operator registered in the manifest, which is what keeps containment
    constrained, reviewable, and auditable.
    """

    id: str
    type: Literal["block_edge", "quarantine_node"]
    label: str
    #: ``block_edge`` severs ``source --action--> target``.
    #: ``quarantine_node`` severs every edge incident to ``target``.
    source: str | None = None
    action: Action | None = None
    target: str
    reversible: bool
    #: Estimated business disruption in arbitrary but comparable units. The
    #: planner prefers the lowest-cost capability that fully works.
    cost: int
    rationale: str = ""


class Invariant(BaseModel):
    """A structural property the architecture must never exhibit."""

    id: str
    description: str = ""
    source_data_class: DataClassification
    sink_zone: str
    required_bridge_registration: Registration
    status: Literal["prohibited", "advisory"]


class ArchitectureManifest(BaseModel):
    """The versioned declaration of what this agent population is meant to do."""

    version: str
    zones: dict[str, Any] = Field(default_factory=dict)
    nodes: list[Node] = Field(default_factory=list)
    allowed_relationships: list[Relationship] = Field(default_factory=list)
    invariants: list[Invariant] = Field(default_factory=list)
    control_capabilities: list[ControlCapability] = Field(default_factory=list)

    # -- lookups ------------------------------------------------------------

    def node(self, node_id: str) -> Node | None:
        """Return the declared node with *node_id*, or ``None`` if undeclared."""
        return next((n for n in self.nodes if n.id == node_id), None)

    def zone_trust(self, zone: str) -> Trust:
        """Trust level declared for *zone*, defaulting to ``internal``."""
        spec = self.zones.get(zone)
        declared = spec.get("trust") if isinstance(spec, dict) else None
        if declared == "untrusted":
            return "untrusted"
        if declared == "external":
            return "external"
        return "internal"

    def allows(self, source: str, action: str, target: str) -> bool:
        """True when the manifest permits this exact relationship."""
        return any(
            r.source == source and r.action == action and r.target == target
            for r in self.allowed_relationships
        )


# ---------------------------------------------------------------------------
# Observations and projections
# ---------------------------------------------------------------------------


class ObservationEvent(BaseModel):
    """One reported interaction.

    An observation proves that an event was *reported*. It never proves intent,
    and HIVE's language preserves that distinction everywhere it surfaces.
    """

    event_id: str
    sequence: int
    occurred_at: str
    actor: str
    action: Action
    target: str
    context: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    result: str = "success"


class ObservedEdge(BaseModel):
    """An ``actor --action--> target`` relationship seen at least once."""

    source: str
    target: str
    action: Action
    first_seen: str
    last_seen: str
    #: ``expected`` when the manifest permits this exact relationship,
    #: ``unexpected`` when it does not.
    expected_status: Literal["expected", "unexpected"]
    observation_count: int = 1
    evidence_event_ids: list[str] = Field(default_factory=list)

    @property
    def key(self) -> str:
        """Stable identifier that distinguishes parallel actions between a pair."""
        return f"{self.source}--{self.action}-->{self.target}"


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


class PathStep(BaseModel):
    """One hop of the composed capability path named by a finding."""

    source: str
    action: Action
    target: str
    role: str
    expected_status: Literal["expected", "unexpected"]
    evidence_event_ids: list[str] = Field(default_factory=list)


class RiskFactor(BaseModel):
    """One inspectable signal contributing to a finding's emergence score."""

    id: str
    label: str
    present: bool
    weight: float
    detail: str = ""


class Finding(BaseModel):
    """A risky *system state*, evidenced and explained.

    A finding never asserts that an agent is malicious. It asserts that the
    observed topology composes a capability the declared architecture forbids.
    """

    id: str
    rule_id: Literal["PS-001", "PS-002"]
    title: str
    status: Literal["open", "contained"]
    severity: Severity
    manifest_version: str
    detected_at_sequence: int
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    emergence_score: float = 0.0
    policy_basis: str
    incident_node_ids: list[str] = Field(default_factory=list)
    incident_edge_ids: list[str] = Field(default_factory=list)
    incident_path: list[PathStep] = Field(default_factory=list)
    evidence_event_ids: list[str] = Field(default_factory=list)
    explanation: str
    uncertainty: str = ""


# ---------------------------------------------------------------------------
# Containment
# ---------------------------------------------------------------------------


class ContainmentCandidate(BaseModel):
    """One registered capability, evaluated counterfactually against the graph."""

    capability_id: str
    label: str
    cost: int
    removes_unsafe_path: bool
    preserves_workflow: bool
    broken_expected_relationships: list[str] = Field(default_factory=list)
    viable: bool
    rejection_reason: str = ""


class ContainmentPlan(BaseModel):
    """Every evaluated candidate plus the recommended minimum action."""

    id: str
    finding_id: str
    manifest_version: str
    candidates: list[ContainmentCandidate] = Field(default_factory=list)
    recommended_capability_id: str | None = None
    cost_breakdown: dict[str, Any] = Field(default_factory=dict)
    impact: str
    state: Literal["proposed", "applied", "verified", "failed"] = "proposed"
    verification: dict[str, Any] = Field(default_factory=dict)


class ControlExecution(BaseModel):
    """The audit record of a simulated control action."""

    id: str
    plan_id: str
    capability_id: str
    state: Literal["success", "failed"]
    issued_at: str
    result_event_ids: list[str] = Field(default_factory=list)
    reversible: bool = True


# ---------------------------------------------------------------------------
# Immunity memory
# ---------------------------------------------------------------------------


class ImmunityPattern(BaseModel):
    """An abstracted precursor pattern recorded after a finding is contained.

    Patterns enter as ``draft``. Promotion to ``shadow`` (detect-only) and then
    ``active`` is an explicit human decision, never an automatic one.
    """

    id: str
    rule_id: Literal["PS-001", "PS-002"]
    lifecycle: Literal["draft", "shadow", "active"]
    title: str
    abstract_preconditions: list[str] = Field(default_factory=list)
    evidence_basis: list[str] = Field(default_factory=list)
    recommended_control_class: str
    created_at: str
    promoted_at: str | None = None
