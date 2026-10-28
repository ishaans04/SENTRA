"""Containment controls, enforced at the gateway instead of simulated.

The HIVE engine shipped a simulated control adapter that appended a ``block``
event and stopped there. This adapter does the same job with a real effect: it
installs a deny rule the gateway checks on every call, then records the same
block in the HIVE ledger so the engine's picture of the estate matches what is
now enforced.
"""

from __future__ import annotations

from aegis.gateway.server import Gateway
from aegis.gateway.state import DenyRule
from aegis.hive_bridge import HiveBridge
from aegis.ledger import LedgerEvent


class GatewayControlAdapter:
    def __init__(self, gateway: Gateway, bridge: HiveBridge) -> None:
        self.gateway = gateway
        self.bridge = bridge

    def apply(self, capability_id: str, cause: LedgerEvent) -> DenyRule:
        """Install *capability_id*. Idempotent: a second apply changes nothing."""
        for rule in self.gateway.state.deny_rules:
            if rule.capability_id == capability_id:
                return rule
        capability = next(
            (c for c in self.bridge.manifest.control_capabilities if c.id == capability_id), None
        )
        if capability is None:
            raise ValueError(f"Capability {capability_id!r} is not pre-authorised in the manifest.")
        rule = DenyRule(
            capability_id=capability.id,
            control_type=capability.type,
            target=capability.target,
            source=capability.source,
            action=capability.action,
        )
        self.gateway.state.deny_rules.append(rule)
        self.bridge.apply_block(capability_id, cause)
        return rule
