"""The outbox: every send waits here before anything goes out.

An agent's ``send`` call never reaches the webhook directly. It becomes a queued
action with a receipt, and only the outbox, acting as the gateway, delivers it.
That gap between asking and sending is what lets a withdrawn approval stop a
report that was already on its way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionStatus = Literal["queued", "held", "released", "delivered", "cancelled"]


@dataclass
class QueuedAction:
    id: str
    run_id: str
    decision_id: str
    actor: str
    tool: str
    args: dict[str, Any]
    status: ActionStatus = "queued"
    cites: list[str] = field(default_factory=list)


class Outbox:
    def __init__(self) -> None:
        self._actions: dict[str, QueuedAction] = {}

    def queue(
        self, run_id: str, decision_id: str, actor: str, tool: str, args: dict[str, Any]
    ) -> QueuedAction:
        action = QueuedAction(
            id=f"A-{len(self._actions) + 1}",
            run_id=run_id,
            decision_id=decision_id,
            actor=actor,
            tool=tool,
            args=dict(args),
        )
        self._actions[action.id] = action
        return action

    def get(self, action_id: str) -> QueuedAction:
        try:
            return self._actions[action_id]
        except KeyError:
            raise KeyError(f"No action {action_id!r}.") from None

    def all(self) -> list[QueuedAction]:
        return list(self._actions.values())

    def for_run(self, run_id: str) -> list[QueuedAction]:
        return [a for a in self._actions.values() if a.run_id == run_id]
