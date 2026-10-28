"""The gateway's decision for one call, as a pure function.

``enforce`` knows nothing about MCP. The middleware calls it for every tool call
and acts on the verdict; the outbox calls it again at release time. Keeping it
transport-free is what makes it testable on its own and what lets the same
rules sit in front of the fictional servers or, through a proxy, real ones.

No model is consulted here, or anywhere this function is called from (INV-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aegis.gateway.state import GatewayState, ToolCall


@dataclass(frozen=True)
class Verdict:
    outcome: Literal["forward", "queue", "reject"]
    reason: str | None = None


def enforce(call: ToolCall, state: GatewayState) -> Verdict:
    run = state.runs.get(call.run_id or "")
    if run is None:
        return Verdict("reject", "unknown_connection")
    if run.status == "cancelled":
        return Verdict("reject", "run_cancelled")
    if call.tool.effect == "send":
        return Verdict("queue")
    return Verdict("forward")
