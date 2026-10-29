"""Containment controls, enforced at the gateway instead of simulated.

The engine's own control adapter is simulated: it appends a ``block`` event and
stops there. This adapter does the same job with a real effect: it installs a
deny rule the gateway checks on every call, then records the same block in the
engine's ledger so the engine's picture of the estate matches what is now
enforced.
"""

from __future__ import annotations

from sentra.engine_bridge import EngineBridge
from sentra.gateway.server import Gateway
from sentra.gateway.state import DenyRule
from sentra.ledger import LedgerEvent


class GatewayControlAdapter:
    def __init__(self, gateway: Gateway, bridge: EngineBridge) -> None:
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
