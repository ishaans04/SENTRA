"""What the gateway knows when it decides a call: runs, and the call itself."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sentra.decisions.models import Decision
from sentra.tools.catalogue import ToolSpec

RunStatus = Literal["running", "stale", "completed", "cancelled"]

#: The recovery executor's identity. Only it may call recovery-only tools, and it
#: is not bound by a decision: it acts on the operator's confirmed plan.
RECOVERY_ACTOR = "sentra-recovery"

#: How a tool's effect class reads as an engine relationship, for control rules.
_EFFECT_AS_ACTION = {"read": "read", "write": "write", "send": "send"}


@dataclass
class RunState:
    """One agent run under one decision, started at one epoch (its fencing token)."""

    id: str
    actor: str
    decision_id: str
    epoch: int
    status: RunStatus = "running"
    fresh_context: bool = False


@dataclass(frozen=True)
class ToolCall:
    run_id: str | None
    actor: str | None
    tool: ToolSpec
    args: dict[str, Any]


@dataclass(frozen=True)
class DenyRule:
    """A containment control installed in the gateway (from the engine's ranked list)."""

    capability_id: str
    control_type: Literal["block_edge", "quarantine_node"]
    target: str
    source: str | None = None
    action: str | None = None

    def denies(self, actor: str | None, tool: ToolSpec) -> bool:
        if tool.resource != self.target:
            return False
        if self.control_type == "quarantine_node":
            return True
        return actor == self.source and _EFFECT_AS_ACTION.get(tool.effect) == self.action


@dataclass(frozen=True)
class StandingRule:
    """A standing order compiled against this estate: these actors never read these resources."""

    order_id: str
    actors: frozenset[str]
    resources: frozenset[str]

    def denies(self, actor: str | None, tool: ToolSpec) -> bool:
        return tool.effect == "read" and actor in self.actors and tool.resource in self.resources


@dataclass
class GatewayState:
    runs: dict[str, RunState] = field(default_factory=dict)
    #: The decision ledger's live view, shared by reference. The gateway reads it;
    #: only the decision service changes it.
    decisions: dict[str, Decision] = field(default_factory=dict)
    deny_rules: list[DenyRule] = field(default_factory=list)
    #: Standing orders the operator confirmed, in this session or an earlier one.
    standing_rules: list[StandingRule] = field(default_factory=list)
    #: (actor, tool, target) triples a person approved for one destructive call each.
    live_approvals: set[tuple[str, str, str]] = field(default_factory=set)
