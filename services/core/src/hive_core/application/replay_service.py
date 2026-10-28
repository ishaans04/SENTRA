"""Use-case orchestration for one replay session.

This is the only layer that knows the order of operations: fold events into the
projection, run the rules, plan containment, issue a control, verify what the
control actually did, and record the pattern. Every step below delegates the
decision itself to the domain module that owns it.

Determinism is the contract. Two sessions constructed from the same manifest and
fixture, advanced to the same cursor, produce identical findings, identical
candidate evaluations, and an identical recommendation. That property is what
turns a demo into evidence, and :meth:`fingerprint` exists so a test can assert
it directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hive_core.connectors.simulated import SimulatedControlAdapter
from hive_core.containment.planner import ContainmentPlanner
from hive_core.detection.base import Detector
from hive_core.detection.ps001 import PS001Detector
from hive_core.detection.ps002 import PS002Detector
from hive_core.domain.models import ContainmentPlan, Finding
from hive_core.graph.projection import GraphProjection
from hive_core.immunity.registry import ImmunityRegistry
from hive_core.lab.scenarios import ScenarioLoader
from hive_core.ledger.repository import LedgerRepository
from hive_core.policy.engine import PolicyEngine


class ReplayService:
    """Drive one scenario against one manifest."""

    def __init__(self, manifest_path: str | Path, scenario_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path)
        self.scenario_path = Path(scenario_path)
        self.scenario_id = self.scenario_path.stem

        self.policy = PolicyEngine()
        self.manifest = self.policy.load_manifest(self.manifest_path)

        loader = ScenarioLoader(self.scenario_path.parent)
        self._fixture = loader.load(self.scenario_id)

        self.detectors: list[Detector] = [PS001Detector(), PS002Detector()]
        self.planner = ContainmentPlanner(self.manifest, self.detectors)
        self.immunity = ImmunityRegistry()

        #: Highest sequence in the scenario itself. Control events are appended
        #: above this band, so the replay bound must come from the fixture
        #: rather than from the end of the ledger — otherwise issuing a control
        #: makes the replay look unfinished.
        self._replay_bound = max((event.sequence for event in self._fixture), default=0)

        self.ledger = LedgerRepository()
        self.graph = GraphProjection(self.manifest)
        self.adapter = SimulatedControlAdapter(self.ledger, self.manifest.control_capabilities)

        #: plan id -> plan, for the life of the current containment state.
        self._plans: dict[str, ContainmentPlan] = {}

        self.reset()

    # ------------------------------------------------------------------
    # Replay control
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Return the session to its initial state.

        Everything derived is discarded and rebuilt from the fixture: the graph,
        the plan cache, the control adapter's execution history, and the immunity
        registry. Nothing from a previous run can leak into the next one, which
        is what makes a second replay a genuine repetition rather than a
        continuation.
        """
        self.ledger = LedgerRepository()
        self.ledger.extend(self._fixture)
        self.graph.reset()
        self.adapter = SimulatedControlAdapter(self.ledger, self.manifest.control_capabilities)
        self.immunity.clear()
        self._plans.clear()

    def step(self) -> list[dict[str, Any]]:
        """Advance one event and return it."""
        stepped = self.ledger.advance()
        self.graph.apply_events(stepped)
        return [event.model_dump() for event in stepped]

    def advance_to(self, sequence: int) -> list[dict[str, Any]]:
        """Advance to *sequence*, returning every event passed over."""
        stepped = self.ledger.advance(sequence)
        self.graph.apply_events(stepped)
        return [event.model_dump() for event in stepped]

    def run_to_end(self) -> list[dict[str, Any]]:
        """Fast-forward through the remainder of the fixture."""
        return self.advance_to(self._replay_bound)

    @property
    def replay_clock(self) -> str:
        """The timestamp of the replay's current position.

        Controls and immunity records are stamped with this rather than with the
        wall clock, so replaying a scenario twice produces a byte-identical
        ledger. A record whose contents depend on when an operator clicked is
        not reproducible evidence.
        """
        replayed = self.ledger.replayed()
        return replayed[-1].occurred_at if replayed else "1970-01-01T00:00:00Z"

    @property
    def at_end(self) -> bool:
        """True when the cursor has passed every scenario event."""
        return self.ledger.cursor >= self._replay_bound

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def state(self) -> dict[str, Any]:
        """Everything the console needs to render the current moment."""
        return {
            "scenario_id": self.scenario_id,
            "manifest_version": self.manifest.version,
            "cursor": self.ledger.cursor,
            "last_sequence": self._replay_bound,
            "replayed_events": len(self.ledger.replayed()),
            "total_events": len(self._fixture),
            "at_end": self.at_end,
            "graph": self.graph.snapshot(),
            "timeline": [event.model_dump() for event in self.ledger.all_events()],
            "invariants": self.policy.check_invariants(self.graph),
            "applied_controls": list(self.graph.applied_controls),
        }

    def detect(self) -> list[Finding]:
        """Run every rule against the current projection.

        Read-only: calling this twice changes nothing. Findings carry the cursor
        at which they were observed so the console can say when a risk appeared.
        """
        findings: list[Finding] = []
        for detector in self.detectors:
            for finding in detector.detect(self.graph):
                finding.detected_at_sequence = self.ledger.cursor
                findings.append(finding)
        return findings

    def plan_for(self, finding: Finding) -> ContainmentPlan:
        """Return the containment plan for *finding*, computing it if needed.

        Plans are cached per finding so that a plan already applied keeps its
        state and verification record. Any plan still in ``proposed`` is
        recomputed, because the graph may have advanced since it was made and a
        stale recommendation is worse than none.
        """
        plan_id = f"plan-{finding.id}"
        cached = self._plans.get(plan_id)
        if cached is not None and cached.state != "proposed":
            return cached
        plan = self.planner.plan(finding, self.graph)
        self._plans[plan.id] = plan
        return plan

    def plans(self) -> list[ContainmentPlan]:
        """Plans for every currently open finding, plus any already applied."""
        current = [self.plan_for(finding) for finding in self.detect()]
        applied = [p for p in self._plans.values() if p.state != "proposed"]
        by_id = {plan.id: plan for plan in [*applied, *current]}
        return sorted(by_id.values(), key=lambda plan: plan.id)

    def findings_envelope(self) -> dict[str, Any]:
        """Findings and their plans, in the shape the console consumes."""
        findings = self.detect()
        plans = self.plans()
        open_ids = {finding.id for finding in findings}
        for plan in plans:
            if plan.finding_id not in open_ids and plan.state == "applied":
                plan.state = "verified"
        return {
            "findings": [finding.model_dump() for finding in findings],
            "plans": [plan.model_dump() for plan in plans],
        }

    # ------------------------------------------------------------------
    # Containment
    # ------------------------------------------------------------------

    def apply_plan(self, plan_id: str) -> ContainmentPlan:
        """Issue the recommended control for *plan_id* and verify the result.

        The control is issued as a ledger event and folded back through the same
        projection that produced the finding, so verification measures the real
        contained state rather than the planner's prediction of it.
        """
        plan = self._plans.get(plan_id)
        if plan is None:
            plan = next(
                (self.plan_for(f) for f in self.detect() if f"plan-{f.id}" == plan_id),
                None,
            )
        if plan is None:
            raise KeyError(f"No containment plan {plan_id!r} for the current state.")

        if plan.state in ("applied", "verified"):
            return plan

        if plan.recommended_capability_id is None:
            plan.state = "failed"
            plan.verification = {
                "attempted": False,
                "reason": (
                    "No registered capability removes this path without breaking a "
                    "declared relationship. HIVE will not act outside its authorisation."
                ),
            }
            return plan

        finding = next((f for f in self.detect() if f.id == plan.finding_id), None)
        expected_before = self._expected_relationships()

        execution = self.adapter.apply(plan.recommended_capability_id, plan.id, self.replay_clock)
        control_events = [
            event
            for event in (self.ledger.event(event_id) for event_id in execution.result_event_ids)
            if event is not None
        ]
        self.graph.apply_events(control_events)

        still_open = {f.id for f in self.detect()}
        expected_after = self._expected_relationships()
        broken = sorted(expected_before - expected_after)

        removed = plan.finding_id not in still_open
        plan.state = "verified" if removed and not broken else "failed"
        plan.verification = {
            "attempted": True,
            "capability_id": plan.recommended_capability_id,
            "control_event_ids": list(execution.result_event_ids),
            "unsafe_path_removed": removed,
            "declared_relationships_before": sorted(expected_before),
            "declared_relationships_after": sorted(expected_after),
            "broken_declared_relationships": broken,
            "workflow_preserved": not broken,
            "reversible": execution.reversible,
        }

        if plan.state == "verified" and finding is not None:
            finding.status = "contained"
            self.immunity.record_from_finding(finding, self.replay_clock)

        return plan

    def _expected_relationships(self) -> set[str]:
        return {edge.key for edge in self.graph.edges if edge.expected_status == "expected"}

    # ------------------------------------------------------------------
    # Determinism
    # ------------------------------------------------------------------

    def fingerprint(self) -> str:
        """A stable digest of everything the session currently concludes.

        Two independent sessions advanced to the same point must produce the same
        fingerprint. Comparing fingerprints is how the test suite proves replay
        determinism without asserting on prose.
        """
        payload = {
            "manifest": self.manifest.version,
            "cursor": self.ledger.cursor,
            "edges": [edge.key for edge in self.graph.edges],
            "findings": [
                {
                    "id": finding.id,
                    "rule": finding.rule_id,
                    "severity": finding.severity,
                    "score": finding.emergence_score,
                    "path": finding.incident_edge_ids,
                    "evidence": finding.evidence_event_ids,
                }
                for finding in self.detect()
            ],
            "recommendations": [
                {"plan": plan.id, "capability": plan.recommended_capability_id}
                for plan in self.plans()
            ],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
