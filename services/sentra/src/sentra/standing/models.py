"""A standing order: one rule the operator said should always hold, and why.

An order is written only from a confirmed read-back. Agents have no tool that
reaches it, so a poisoned page or a stray note cannot plant one. Each order
keeps its provenance: the session, the finding and the recovery it came from,
and the calls that finding cited.

``compile_order`` resolves an order against one estate's manifest into the
``StandingRule`` the gateway checks. The rule is recompiled in every session,
so a new agent that may send outside is covered by "every agent that can send
outside" without anyone editing the order.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sentra.gateway.state import StandingRule
from sentra_core.domain.models import ArchitectureManifest

OrderStatus = Literal["proposed", "active", "revoked", "discarded"]


class NoUndeclaredReads(BaseModel):
    """No covered agent reads from storage the manifest does not declare.

    With no ``actor``, it covers every agent the manifest lets send outside.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["NoUndeclaredReads"] = "NoUndeclaredReads"
    actor: str | None = None

    def typed(self) -> str:
        return f"NoUndeclaredReads({self.actor or 'senders'})"


class OrderProvenance(BaseModel):
    session_id: str
    decided_at: str
    finding_id: str | None = None
    rule_id: str | None = None
    plan_id: str | None = None
    #: The ledger events the finding cited.
    evidence: list[str] = Field(default_factory=list)
    #: The runs the recovery cancelled.
    runs: list[str] = Field(default_factory=list)


class StandingOrderProposal(BaseModel):
    """What interpretation produces from a dictated standing order."""

    rule: NoUndeclaredReads
    plain: str


class StandingOrder(BaseModel):
    id: str
    rule: NoUndeclaredReads
    #: The order in the operator's terms, used in read-backs.
    plain: str
    dictated_text: str
    status: OrderStatus = "proposed"
    provenance: OrderProvenance


def compile_order(order: StandingOrder, manifest: ArchitectureManifest) -> StandingRule:
    if order.rule.actor is not None:
        actors = frozenset({order.rule.actor})
    else:
        actors = frozenset(r.source for r in manifest.allowed_relationships if r.action == "send")
    resources = frozenset(n.id for n in manifest.nodes if n.registration == "unregistered")
    return StandingRule(order_id=order.id, actors=actors, resources=resources)
