"""The session ledger: one append-only log for everything that happens in a session.

Gateway calls, engine findings, decision changes, recovery steps and checks are
all ``LedgerEvent`` rows in one ordered list (PRD §11.1). Nothing else is state:
decisions, runs and actions are rebuilt by folding these events, so a session
exported as JSONL replays into an identical one (INV-5).

Sequence numbers and timestamps come from the session alone, a counter and the
seeded ``LogicalClock``, never from the wall clock.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from sentra.clock import LogicalClock

Producer = Literal[
    "gateway",
    "engine",
    "sentra",
    "recovery",
    "interpret",
    "operator",
    "human",
    "verification",
    "scenario",
]

#: The event catalogue (PRD §11.2). An unknown kind is a bug, not a new feature.
EVENT_KINDS = frozenset(
    {
        "session.seeded",
        "gateway.call",
        "action.queued",
        "action.held",
        "action.released",
        "action.cancelled",
        "action.delivered",
        "run.started",
        "run.completed",
        "run.cancelled",
        "item.version_changed",
        "finding.raised",
        "containment.proposed",
        "containment.applied",
        "containment.verified",
        "containment.failed",
        "decision.proposed",
        "decision.confirmed",
        "decision.needs_review",
        "decision.suspended",
        "decision.renewed",
        "decision.withdrawn",
        "decision.discarded",
        "condition.evaluated",
        "basis.withdrawn",
        "evidence.recorded",
        "alert.raised",
        "interpretation.requested",
        "interpretation.result",
        "recovery.plan_drafted",
        "recovery.plan_confirmed",
        "recovery.plan_abandoned",
        "recovery.step_started",
        "recovery.step_succeeded",
        "recovery.step_conflict",
        "recovery.step_failed",
        "recovery.step_escalated",
        "conflict.resolved",
        "verification.check",
        "record.closed",
        "standing_order.loaded",
        "standing_order.proposed",
        "standing_order.confirmed",
        "standing_order.discarded",
        "standing_order.revoked",
    }
)


class LedgerEvent(BaseModel):
    seq: int
    event_id: str
    session_id: str
    at: str
    kind: str
    producer: Producer
    actor: str | None = None
    run_id: str | None = None
    decision_id: str | None = None
    epoch: int | None = None
    cites: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionLedger:
    def __init__(self, session_id: str, clock: LogicalClock) -> None:
        self.session_id = session_id
        self.clock = clock
        self._events: list[LedgerEvent] = []
        self._subscribers: list[asyncio.Queue[LedgerEvent | None]] = []
        self.closed = False
        #: Called synchronously on every append, in order. Projections that must
        #: never lag the ledger (the decision graph) register here.
        self.listeners: list[Callable[[LedgerEvent], None]] = []

    def append(
        self,
        kind: str,
        producer: Producer,
        *,
        actor: str | None = None,
        run_id: str | None = None,
        decision_id: str | None = None,
        epoch: int | None = None,
        cites: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> LedgerEvent:
        if kind not in EVENT_KINDS:
            raise ValueError(f"Unknown event kind {kind!r}.")
        seq = len(self._events) + 1
        event = LedgerEvent(
            seq=seq,
            event_id=f"ev-{seq:06d}",
            session_id=self.session_id,
            at=self.clock.tick(),
            kind=kind,
            producer=producer,
            actor=actor,
            run_id=run_id,
            decision_id=decision_id,
            epoch=epoch,
            cites=list(cites or []),
            payload=dict(payload or {}),
        )
        self._events.append(event)
        for listener in self.listeners:
            listener(event)
        for queue in self._subscribers:
            queue.put_nowait(event)
        return event

    def events(self) -> list[LedgerEvent]:
        return list(self._events)

    def get(self, event_id: str) -> LedgerEvent | None:
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    def subscribe(self) -> asyncio.Queue[LedgerEvent | None]:
        queue: asyncio.Queue[LedgerEvent | None] = asyncio.Queue()
        if self.closed:
            queue.put_nowait(None)
        else:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[LedgerEvent | None]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def close(self) -> None:
        """The session is gone: end every open stream with a ``None`` sentinel."""
        self.closed = True
        for queue in self._subscribers:
            queue.put_nowait(None)
        self._subscribers.clear()

    def to_jsonl(self) -> str:
        return "".join(json.dumps(e.model_dump(), sort_keys=True) + "\n" for e in self._events)

    @staticmethod
    def parse_jsonl(text: str) -> list[LedgerEvent]:
        return [LedgerEvent(**json.loads(line)) for line in text.splitlines() if line.strip()]
