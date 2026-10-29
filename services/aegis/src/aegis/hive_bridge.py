"""Feeds gateway calls to the HIVE engine, unchanged, and reads its answers back.

HIVE was built to replay fixture files. Here its input is live: every call the
gateway records becomes one HIVE observation, validated and redacted by HIVE's
own ingest, appended to HIVE's own ledger and folded into HIVE's own graph.
Nothing in ``hive_core`` is modified; this module only calls it.

What becomes an observation, and what does not:

- ``read``, ``write`` and ``send`` calls map to the HIVE action of the same name.
  A queued send counts as an egress attempt: the route exists whether or not
  the outbox has released it yet.
- ``grant`` calls are not data movement, so they are not hops.
- Rejected calls never reached a tool, so they create no edge.

Each finding id is reported once. The AEGIS arbiter's one rule that survives
here is de-duplication: one alert per finding, however many calls re-confirm it.
"""

from __future__ import annotations

from pathlib import Path

from aegis.ledger import LedgerEvent
from hive_core.containment.planner import ContainmentPlanner
from hive_core.detection.base import Detector
from hive_core.detection.ps001 import PS001Detector
from hive_core.detection.ps002 import PS002Detector
from hive_core.domain.models import (
    ArchitectureManifest,
    ContainmentPlan,
    Finding,
    ObservationEvent,
)
from hive_core.graph.projection import GraphProjection
from hive_core.ingest.validator import EventValidator
from hive_core.ledger.repository import LedgerRepository
from hive_core.policy.engine import PolicyEngine

_HIVE_ACTION = {"read": "read", "write": "write", "send": "send"}
_COUNTED_OUTCOMES = frozenset({"executed", "queued"})


class HiveBridge:
    def __init__(self, manifest_path: str | Path) -> None:
        self.manifest: ArchitectureManifest = PolicyEngine().load_manifest(manifest_path)
        self.detectors: list[Detector] = [PS001Detector(), PS002Detector()]
        self.planner = ContainmentPlanner(self.manifest, self.detectors)
        self.ledger = LedgerRepository()
        self.projection = GraphProjection(self.manifest)
        self._seen: set[str] = set()
        self._findings: dict[str, Finding] = {}

    def observe(self, call: LedgerEvent) -> list[Finding]:
        """Fold one gateway call into HIVE and return findings that are new."""
        action = _HIVE_ACTION.get(str(call.payload.get("effect")))
        if action is None or call.payload.get("outcome") not in _COUNTED_OUTCOMES:
            return []
        raw = {
            "event_id": call.event_id,
            "sequence": call.seq,
            "occurred_at": call.at,
            "actor": call.actor,
            "action": action,
            "target": call.payload["resource"],
            "context": {
                key: value
                for key, value in call.payload.items()
                if key not in {"effect", "resource"}
            }
            | {"run_id": call.run_id},
            "provenance": {"adapter": "sentra-gateway", "ledger_event": call.event_id},
            "result": "success",
        }
        self._fold(EventValidator.validate(raw))
        return self._new_findings()

    def apply_block(self, capability_id: str, cause: LedgerEvent) -> None:
        """Record a containment control in HIVE's ledger and graph.

        The gateway enforces the control; this keeps HIVE's picture of the estate
        in step with it, so re-running the rules measures the contained state.
        """
        capability = next(
            (c for c in self.manifest.control_capabilities if c.id == capability_id), None
        )
        if capability is None:
            raise ValueError(f"Capability {capability_id!r} is not registered in this manifest.")
        context: dict[str, object] = {
            "capability_id": capability.id,
            "control_type": capability.type,
            "label": capability.label,
            "reversible": capability.reversible,
            "simulated": False,
        }
        if capability.type == "block_edge":
            context["source"] = capability.source
            context["blocked_action"] = capability.action
        self._fold(
            ObservationEvent(
                event_id=f"ctl::{cause.event_id}::{capability.id}",
                sequence=cause.seq,
                occurred_at=cause.at,
                actor="SENTRA Gateway",
                action="block",
                target=capability.target,
                context=context,
                provenance={"issued_by": "sentra-gateway", "ledger_event": cause.event_id},
                result="success",
            )
        )
        self._findings = {f.id: f for f in self._detect()}

    def plan(self, finding_id: str) -> ContainmentPlan:
        finding = self._findings.get(finding_id)
        if finding is None:
            raise KeyError(f"No open finding {finding_id!r}.")
        return self.planner.plan(finding, self.projection)

    def finding(self, finding_id: str) -> Finding | None:
        return self._findings.get(finding_id)

    def open_findings(self) -> list[Finding]:
        return list(self._findings.values())

    def rerun_rules(self) -> list[Finding]:
        """Run every rule against the current graph, without reporting anything."""
        return self._detect()

    def observations(self) -> list[ObservationEvent]:
        return [e for e in self.ledger.all_events() if e.action != "block"]

    def observation_count(self) -> int:
        return len(self.observations())

    def _fold(self, event: ObservationEvent) -> None:
        self.ledger.append(event)
        self.projection.apply_events(self.ledger.advance(event.sequence))

    def _detect(self) -> list[Finding]:
        found: list[Finding] = []
        for detector in self.detectors:
            for finding in detector.detect(self.projection):
                finding.detected_at_sequence = self.ledger.cursor
                found.append(finding)
        return found

    def _new_findings(self) -> list[Finding]:
        current = self._detect()
        self._findings = {f.id: f for f in current}
        fresh = [f for f in current if f.id not in self._seen]
        self._seen.update(f.id for f in fresh)
        return fresh
