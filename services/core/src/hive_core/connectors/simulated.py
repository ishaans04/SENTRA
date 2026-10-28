"""Simulated control point.

In a real deployment this adapter would call an enforcement surface — a service
mesh policy, an API gateway rule, an agent framework's permission store. Here it
does something deliberately smaller and entirely local: it appends a ``block``
observation to the ledger describing exactly which relationship was severed.

Two consequences follow, and both are the point.

First, **nothing leaves this machine.** No endpoint is contacted, no
configuration is mutated, no credential is used. The demonstration is honest
about being a simulation.

Second, **the control is itself evidence.** Because the block is an event in the
same append-only ledger as every observation, the record of why the graph
changed sits beside the record of what changed, and a replay reproduces the
contained state exactly.
"""

from __future__ import annotations

from hive_core.domain.models import ControlCapability, ControlExecution, ObservationEvent
from hive_core.ledger.repository import LedgerRepository

#: Control events are sequenced above any fixture event so replay ordering keeps
#: them after the observations that motivated them.
_CONTROL_SEQUENCE_BASE = 10_000


class SimulatedControlAdapter:
    """Issue simulated control actions as ledger events."""

    def __init__(
        self,
        ledger: LedgerRepository,
        capabilities: list[ControlCapability],
    ) -> None:
        self._ledger = ledger
        self._capabilities = {capability.id: capability for capability in capabilities}
        self._executions: dict[str, ControlExecution] = {}
        self._issued = 0

    # ------------------------------------------------------------------

    def apply(self, capability_id: str, plan_id: str, occurred_at: str) -> ControlExecution:
        """Issue *capability_id* for *plan_id* and return the execution record.

        *occurred_at* comes from the replay position the control was issued at,
        not from the wall clock. A ledger whose contents depend on when someone
        clicked cannot be replayed byte-for-byte, and reproducibility is the
        property the whole evidence argument rests on.

        Idempotent: issuing the same capability for the same plan twice returns
        the original record and appends no second event. An operator clicking
        twice must not produce two audit entries for one decision.
        """
        capability = self._capabilities.get(capability_id)
        if capability is None:
            raise ValueError(
                f"Capability {capability_id!r} is not registered in this manifest. "
                "HIVE may only issue pre-authorised controls."
            )

        execution_id = f"exec::{plan_id}::{capability_id}"
        existing = self._executions.get(execution_id)
        if existing is not None:
            return existing

        event = self._control_event(capability, plan_id, occurred_at)
        self._ledger.append(event)

        execution = ControlExecution(
            id=execution_id,
            plan_id=plan_id,
            capability_id=capability_id,
            state="success",
            issued_at=occurred_at,
            result_event_ids=[event.event_id],
            reversible=capability.reversible,
        )
        self._executions[execution_id] = execution
        return execution

    def executions(self) -> list[ControlExecution]:
        return sorted(self._executions.values(), key=lambda e: e.issued_at)

    # ------------------------------------------------------------------

    def _control_event(
        self, capability: ControlCapability, plan_id: str, occurred_at: str
    ) -> ObservationEvent:
        """Build the ledger event that describes this control action.

        The context carries the precise edge to sever so that replaying the
        ledger reconstructs the contained graph without consulting the planner.
        """
        self._issued += 1
        context: dict[str, object] = {
            "capability_id": capability.id,
            "control_type": capability.type,
            "label": capability.label,
            "reversible": capability.reversible,
            "simulated": True,
        }
        if capability.type == "block_edge":
            context["source"] = capability.source
            context["blocked_action"] = capability.action

        return ObservationEvent(
            event_id=f"ctl::{plan_id}::{capability.id}",
            sequence=_CONTROL_SEQUENCE_BASE + self._issued,
            occurred_at=occurred_at,
            actor="HIVE Control Plane",
            action="block",
            target=capability.target,
            context=context,
            provenance={"plan_id": plan_id, "issued_by": "simulated-control-adapter"},
            result="success",
        )
