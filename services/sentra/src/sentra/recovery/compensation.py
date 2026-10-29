"""The compensation registry: which effects can be undone, and how.

Recovery is operation-specific (PRD §19.1). An effect is undone only by the
inverse the tool catalogue registers for it: ``write_draft`` by
``restore_draft``, ``grant_access`` by ``revoke_access``. A send is
irreversible. An effect with no registered inverse is escalated to a person,
never improvised.

Before any inverse runs, the current state is compared with what the agent
produced (the Compensating Transaction pattern). If someone has changed the
item since, the step stops as a conflict and the item is left exactly as the
person left it (INV-8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sentra.agents.scripted import ScriptedAgent
from sentra.gateway.outbox import Outbox
from sentra.ledger import LedgerEvent
from sentra.tools.catalogue import Catalogue

StepStatus = Literal["succeeded", "conflict", "failed", "escalated", "skipped"]


@dataclass(frozen=True)
class StepResult:
    status: StepStatus
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


class CompensationRegistry:
    def __init__(self, catalogue: Catalogue) -> None:
        self.catalogue = catalogue

    def inverse_of(self, tool: str) -> str | None:
        inverse = self.catalogue.get(tool).inverse
        return None if inverse in (None, "irreversible") else inverse

    def is_irreversible(self, tool: str) -> bool:
        return self.catalogue.get(tool).irreversible

    def predicts_conflict(
        self, call: LedgerEvent, current_version: int, writer: str | None
    ) -> bool:
        produced = int((call.payload.get("result") or {}).get("version", 0))
        return current_version != produced or writer != call.actor

    async def compensate(self, call: LedgerEvent, recovery: ScriptedAgent) -> StepResult:
        """Undo one executed call, after checking nothing has changed since."""
        tool = str(call.payload["tool"])
        inverse = self.inverse_of(tool)
        if self.is_irreversible(tool):
            return StepResult("escalated", f"{tool} cannot be undone. A person has to follow up.")
        if inverse is None:
            return StepResult(
                "escalated", f"No undo is registered for {tool}. A person has to decide."
            )
        args = dict(call.payload.get("args") or {})
        world = recovery.gateway.world

        if self.catalogue.get(tool).effect == "grant":
            result = await recovery.call(inverse, {"grantee": args["grantee"]})
            if not result.ok:
                return StepResult("failed", f"{inverse} was refused: {result.error}")
            return StepResult("succeeded", f"Access for {args['grantee']} revoked.", dict(args))

        item_id = str(args["item"])
        item = world.items.get(item_id)
        produced = int((call.payload.get("result") or {}).get("version", 0))
        current_version = item.version if item else 0
        current_writer = item.writer if item else None
        evidence = {
            "item": item_id,
            "produced_version": produced,
            "current_version": current_version,
            "current_writer": current_writer,
        }
        if self.predicts_conflict(call, current_version, current_writer):
            return StepResult(
                "conflict",
                f"{item_id} was changed by {current_writer} after the agent wrote it. "
                "It was not overwritten.",
                evidence,
            )
        result = await recovery.call(inverse, {"item": item_id, "to_version": produced - 1})
        if not result.ok:
            return StepResult("failed", f"{inverse} was refused: {result.error}", evidence)
        return StepResult(
            "succeeded", f"{item_id} restored to its version before the agent.", evidence
        )

    async def compensate_send(self, action_id: str, outbox: Outbox) -> StepResult:
        """A send is irreversible. If it already went out, say so and escalate."""
        action = outbox.get(action_id)
        if action.status == "delivered":
            return StepResult(
                "escalated",
                f"{action_id} was already delivered and cannot be recalled. "
                "A person must follow up with the recipient.",
                {"action_id": action_id},
            )
        return StepResult("skipped", f"{action_id} never went out.", {"action_id": action_id})
