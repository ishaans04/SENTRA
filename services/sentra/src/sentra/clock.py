"""The session clock.

Every timestamp a session writes comes from here, never from the wall clock.
That is what makes a session replayable byte for byte: the same storyline
produces the same ``occurred_at`` on every run, and the engine's ledger, which
orders and cites events by those values, sees identical input.

One place owns time, and the clock never runs backwards whatever order
observations arrive in. It is driven only by ``tick`` (one logical second per
event) and ``observe`` (a replayed timestamp), so there is no live mode to drift.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _parse(value: str) -> datetime:
    return datetime.strptime(value, _FORMAT).replace(tzinfo=UTC)


class LogicalClock:
    """Seeded, monotonic, one second per tick."""

    def __init__(self, start: str = "2026-10-28T10:00:00Z") -> None:
        self._now = _parse(start)

    def now(self) -> str:
        """The current time, without advancing it."""
        return self._now.strftime(_FORMAT)

    def tick(self) -> str:
        """Advance one logical second and return the new time."""
        self._now += timedelta(seconds=1)
        return self.now()

    def observe(self, value: str) -> None:
        """Move forward to a replayed timestamp. Never rewinds."""
        self._now = max(self._now, _parse(value))
