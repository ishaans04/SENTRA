"""Constrained, counterfactual containment planning.

Three properties make this defensible rather than decorative:

**Constrained.** The planner may only choose from the control capabilities an
operator registered in the manifest. It cannot invent an action, and it has no
general kill switch.

**Counterfactual.** Each candidate is evaluated by cloning the live projection,
applying that control to the clone, and re-running the detector. "Does this
work?" is answered by simulation, not by a rule about which edge looks
important.

**Faithful.** The simulation calls the same graph primitive the control adapter
calls when the plan is applied for real. A ``block_edge`` control is scoped to
``source --action--> target`` in both places, so what the planner predicts is
exactly what happens. That equivalence is the reason the post-containment
verification can be trusted.

Selection rule: among the candidates that remove every unsafe path *and* leave
every observed expected relationship intact, take the cheapest. Ties break on
capability id so a replay always yields the same recommendation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hive_core.domain.models import (
    ArchitectureManifest,
    ContainmentCandidate,
    ContainmentPlan,
    ControlCapability,
    Finding,
)
from hive_core.graph.projection import GraphProjection

if TYPE_CHECKING:
    from hive_core.detection.base import Detector


class ContainmentPlanner:
    """Evaluate every registered control against a finding and recommend one."""

    def __init__(
        self,
        manifest: ArchitectureManifest,
        detectors: list[Detector],
    ) -> None:
        self.manifest = manifest
        self.detectors = detectors

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def plan(self, finding: Finding, projection: GraphProjection) -> ContainmentPlan:
        """Evaluate all capabilities against *finding* and return a fresh plan."""
        detector = self._detector_for(finding.rule_id)
        baseline = self._observed_expected_relationships(projection)

        candidates = [
            self._evaluate(capability, detector, projection, baseline)
            for capability in self.manifest.control_capabilities
        ]

        viable = sorted(
            (c for c in candidates if c.viable),
            key=lambda c: (c.cost, c.capability_id),
        )
        recommended = viable[0] if viable else None

        if recommended is not None:
            impact = (
                f"{recommended.label} removes every path this finding names, at an "
                f"estimated disruption cost of {recommended.cost}. Every declared "
                f"relationship currently in use remains intact."
            )
            cost_breakdown = {
                "recommended_cost": recommended.cost,
                "cheapest_rejected_cost": next(
                    (c.cost for c in sorted(candidates, key=lambda c: c.cost) if not c.viable),
                    None,
                ),
                "candidates_evaluated": len(candidates),
                "candidates_viable": len(viable),
            }
        else:
            impact = (
                "No registered capability removes this path without breaking a "
                "declared relationship. Escalate to an operator rather than acting."
            )
            cost_breakdown = {
                "candidates_evaluated": len(candidates),
                "candidates_viable": 0,
            }

        return ContainmentPlan(
            id=f"plan-{finding.id}",
            finding_id=finding.id,
            manifest_version=self.manifest.version,
            candidates=sorted(candidates, key=lambda c: (not c.viable, c.cost, c.capability_id)),
            recommended_capability_id=recommended.capability_id if recommended else None,
            cost_breakdown=cost_breakdown,
            impact=impact,
            state="proposed",
        )

    # ------------------------------------------------------------------
    # Candidate evaluation
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        capability: ControlCapability,
        detector: Detector,
        projection: GraphProjection,
        baseline: set[str],
    ) -> ContainmentCandidate:
        simulated = projection.copy()
        apply_control(simulated, capability)

        removes = not detector.detect(simulated)
        surviving = self._observed_expected_relationships(simulated)
        broken = sorted(baseline - surviving)
        preserves = not broken

        if removes and preserves:
            reason = ""
        elif not removes and broken:
            reason = "Leaves the unsafe path intact and breaks declared relationships."
        elif not removes:
            reason = "The unsafe path survives this control."
        else:
            reason = "Breaks declared relationships that are currently in use: " + ", ".join(broken)

        return ContainmentCandidate(
            capability_id=capability.id,
            label=capability.label,
            cost=capability.cost,
            removes_unsafe_path=removes,
            preserves_workflow=preserves,
            broken_expected_relationships=broken,
            viable=removes and preserves,
            rejection_reason=reason,
        )

    def _observed_expected_relationships(self, projection: GraphProjection) -> set[str]:
        """Declared relationships that are currently live in the projection.

        Comparing this set before and after a simulated control is what proves a
        candidate preserves legitimate work: any declared relationship that
        disappears is collateral damage, and the candidate is rejected for it.
        """
        return {edge.key for edge in projection.edges if edge.expected_status == "expected"}

    def _detector_for(self, rule_id: str) -> Detector:
        for detector in self.detectors:
            if detector.rule_id == rule_id:
                return detector
        raise ValueError(f"No detector registered for rule {rule_id!r}")


# ---------------------------------------------------------------------------
# The single definition of what a control does to a graph
# ---------------------------------------------------------------------------


def apply_control(projection: GraphProjection, capability: ControlCapability) -> int:
    """Apply *capability* to *projection* and return the number of edges severed.

    Both the planner's simulation and the live control adapter route through this
    function, which is what guarantees a simulated outcome and a real one cannot
    drift apart.
    """
    if capability.type == "quarantine_node":
        return projection.quarantine_node(capability.target)

    if capability.source is None or capability.action is None:
        raise ValueError(
            f"block_edge capability {capability.id!r} must declare 'source' and 'action'"
        )
    severed = projection.remove_edge(capability.source, capability.target, capability.action)
    return 1 if severed else 0
