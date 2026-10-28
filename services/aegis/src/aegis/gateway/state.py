"""What the gateway knows when it decides a call: runs, and the call itself."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from aegis.tools.catalogue import ToolSpec

RunStatus = Literal["running", "stale", "completed", "cancelled"]


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


@dataclass
class GatewayState:
    runs: dict[str, RunState] = field(default_factory=dict)
