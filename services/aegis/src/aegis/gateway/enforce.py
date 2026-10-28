"""The gateway's decision for one call, as a pure function.

``enforce`` knows nothing about MCP. The middleware calls it for every tool call
and acts on the verdict; the outbox calls it again at release time. Keeping it
transport-free is what makes it testable on its own and what lets the same
rules sit in front of the fictional servers or, through a proxy, real ones.

The order of checks is PRD §9.6. No model is consulted here, or anywhere this
function is called from (INV-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aegis.gateway.state import RECOVERY_ACTOR, GatewayState, ToolCall

_NOT_LIVE = frozenset({"proposed", "suspended", "withdrawn", "discarded"})


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
    if run.actor == RECOVERY_ACTOR:
        if call.tool.effect in {"send", "destructive"}:
            return Verdict("reject", "recovery_cannot_send")
        return Verdict("forward")

    decision = state.decisions.get(run.decision_id)
    if decision is None:
        return Verdict("reject", "decision_not_live")
    if run.epoch < decision.epoch:
        return Verdict("reject", "stale_epoch")
    if decision.status in _NOT_LIVE:
        return Verdict("reject", "decision_not_live")
    if call.tool.recovery_only:
        return Verdict("reject", "recovery_only")
    if any(rule.denies(run.actor, call.tool) for rule in state.deny_rules):
        return Verdict("reject", "control_deny")
    if call.tool.effect == "destructive":
        target = str(call.args.get("item") or call.args.get("target") or call.tool.resource)
        if (run.actor, call.tool.name, target) not in state.live_approvals:
            return Verdict("reject", "no_live_approval")
    if call.tool.effect == "send":
        return Verdict("queue")
    return Verdict("forward")
