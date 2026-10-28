"""The append-only observation ledger.

The ledger is HIVE's evidence. Everything else — the graph, findings, plans —
is a derived view that can be thrown away and rebuilt from these events. That
separation is what makes a finding reproducible: cite the ledger and the
manifest version, and anyone can regenerate the same conclusion.

Two rules hold:

* **Append-only.** An accepted event is never mutated or removed. Control events
  HIVE itself issues are appended like any other observation, so the record of
  *why* the graph changed lives in the same place as the record of what changed.
* **Idempotent.** Re-appending a known ``event_id`` is a no-op. A replay that
  restarts mid-stream cannot corrupt the record.

The read cursor is replay position, not ledger state. Rewinding the cursor
re-reads history; it never erases it.
"""

from __future__ import annotations

import threading

from hive_core.domain.models import ObservationEvent


class LedgerRepository:
    """An in-memory append-only event log with a replay cursor."""

    def __init__(self) -> None:
        self._events: list[ObservationEvent] = []
        self._index: set[str] = set()
        self._cursor: int = 0
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def append(self, event: ObservationEvent) -> bool:
        """Append *event*. Returns ``False`` if its id was already recorded."""
        with self._lock:
            if event.event_id in self._index:
                return False
            self._events.append(event)
            self._index.add(event.event_id)
            self._events.sort(key=lambda e: (e.sequence, e.event_id))
            return True

    def extend(self, events: list[ObservationEvent]) -> int:
        """Append many events, returning how many were newly recorded.

        Duplicate ``event_id`` values are rejected individually rather than
        failing the batch, so a partially-replayed stream can be re-offered
        safely. A fixture that silently loses events to deduplication is a bug
        in the fixture, and :meth:`duplicate_event_ids` exists to catch it.
        """
        return sum(1 for event in events if self.append(event))

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    @property
    def cursor(self) -> int:
        """Sequence number of the most recently replayed event."""
        with self._lock:
            return self._cursor

    @property
    def total(self) -> int:
        with self._lock:
            return len(self._events)

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._events[-1].sequence if self._events else 0

    def all_events(self) -> list[ObservationEvent]:
        with self._lock:
            return list(self._events)

    def replayed(self) -> list[ObservationEvent]:
        """Events at or before the current cursor."""
        with self._lock:
            return [e for e in self._events if e.sequence <= self._cursor]

    def pending(self) -> list[ObservationEvent]:
        """Events after the current cursor, in order."""
        with self._lock:
            return [e for e in self._events if e.sequence > self._cursor]

    def event(self, event_id: str) -> ObservationEvent | None:
        with self._lock:
            return next((e for e in self._events if e.event_id == event_id), None)

    # ------------------------------------------------------------------
    # Cursor control
    # ------------------------------------------------------------------

    def rewind(self) -> None:
        """Move the read cursor back to the start. The log is untouched."""
        with self._lock:
            self._cursor = 0

    def advance(self, to_sequence: int | None = None) -> list[ObservationEvent]:
        """Move the cursor forward and return the events it passed over.

        With no argument the cursor advances to the next event. With
        *to_sequence* it advances to that sequence number, yielding every event
        in between so a caller can fold them into a projection in order.
        """
        with self._lock:
            upcoming = [e for e in self._events if e.sequence > self._cursor]
            if not upcoming:
                return []
            if to_sequence is None:
                # Step over every event sharing the next sequence, not just the
                # first. Taking one would drop its siblings from `upcoming`
                # forever, so stepping and jumping would build different graphs
                # from the same ledger.
                nxt = upcoming[0].sequence
                stepped = [e for e in upcoming if e.sequence == nxt]
            else:
                stepped = [e for e in upcoming if e.sequence <= to_sequence]
            if not stepped:
                return []
            self._cursor = stepped[-1].sequence
            return stepped

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    @staticmethod
    def duplicate_event_ids(events: list[ObservationEvent]) -> list[str]:
        """Event ids appearing more than once in *events*.

        Deduplication protects the ledger, but it also hides malformed input: a
        fixture with repeated ids loses events silently. Callers load fixtures
        through this check so the failure is loud instead.
        """
        seen: set[str] = set()
        duplicates: list[str] = []
        for event in events:
            if event.event_id in seen and event.event_id not in duplicates:
                duplicates.append(event.event_id)
            seen.add(event.event_id)
        return duplicates

    @staticmethod
    def duplicate_sequences(events: list[ObservationEvent]) -> list[int]:
        """Sequence numbers appearing more than once in *events*.

        Deduplication is keyed on event id, so a fixture can repeat a sequence
        without losing anything — and then replay ambiguously, because "advance
        one event" and "advance to sequence N" would disagree about how many
        events that is. Callers reject such a fixture at load time.
        """
        seen: set[int] = set()
        duplicates: list[int] = []
        for event in events:
            if event.sequence in seen and event.sequence not in duplicates:
                duplicates.append(event.sequence)
            seen.add(event.sequence)
        return duplicates
