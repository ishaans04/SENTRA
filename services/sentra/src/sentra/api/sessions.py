"""Per-visitor sandboxes (PRD §8.14).

Every visitor gets their own seeded ``Session``, keyed by a cookie, so judges
using the site at the same time never see each other's events (NFR-06). Idle
sessions are evicted, and the number of live sessions is capped to fit one
free container; when the cap is reached the least recently used goes first.

Commands on one session run one at a time, under that session's lock, so a
double click or two tabs cannot interleave half-finished steps.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sentra.scenario import Session
from sentra.standing.book import StandingOrderBook

DEFAULT_FIXTURES = Path(__file__).resolve().parents[5] / "fixtures" / "reporting"


@dataclass
class Sandbox:
    session: Session
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = 0.0
    interpret_calls: deque[float] = field(default_factory=deque)


class RateLimited(Exception):
    """Too many requests in the last minute."""


class SessionsFull(Exception):
    """Every sandbox slot is taken by a visitor who is still active."""


#: Open event streams allowed on one session (a few tabs, not a flood).
MAX_STREAMS_PER_SESSION = 4


class SessionManager:
    def __init__(
        self,
        fixtures_dir: str | Path | None = None,
        *,
        cap: int | None = None,
        idle_minutes: int | None = None,
        interpret_per_minute: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.fixtures_dir = Path(fixtures_dir or os.getenv("SENTRA_FIXTURES") or DEFAULT_FIXTURES)
        self.cap = cap or int(os.getenv("SENTRA_SESSION_CAP", "40"))
        self.idle_seconds = 60 * (
            idle_minutes or int(os.getenv("SENTRA_SESSION_IDLE_MINUTES", "30"))
        )
        self.interpret_per_minute = interpret_per_minute or int(
            os.getenv("SENTRA_INTERPRET_PER_MINUTE", "10")
        )
        self.creates_per_minute = int(os.getenv("SENTRA_SESSIONS_PER_MINUTE", "30"))
        self.clock = clock
        self._sandboxes: OrderedDict[str, Sandbox] = OrderedDict()
        self._creates: deque[float] = deque()

    def new_id(self) -> str:
        return "s-" + secrets.token_urlsafe(9)

    def create(self, replacing: str | None = None) -> Sandbox:
        """A fresh seeded sandbox under a new, server-minted id.

        *replacing* is the visitor's current session, if any: it is closed (its
        open streams end) and its slot reused. A new visitor is refused rather
        than evicting someone who is still using the site.

        The visitor's standing orders come with them. A visitor who has kept an
        order starts the week after the incident, ``next-week.yaml``.
        """
        self._evict()
        now = self.clock()
        while self._creates and now - self._creates[0] > 60:
            self._creates.popleft()
        if len(self._creates) >= self.creates_per_minute:
            raise RateLimited()
        old = self._sandboxes.pop(replacing, None) if replacing else None
        if old is not None:
            old.session.ledger.close()
        elif len(self._sandboxes) >= self.cap:
            raise SessionsFull()
        self._creates.append(now)
        session_id = self.new_id()
        orders = old.session.orders if old is not None else StandingOrderBook()
        storyline = "next-week.yaml" if orders.active() else "storyline.yaml"
        session = Session(session_id, self.fixtures_dir, orders=orders, storyline=storyline)
        sandbox = Sandbox(session, last_used=now)
        self._sandboxes[session_id] = sandbox
        return sandbox

    def get(self, session_id: str | None) -> Sandbox | None:
        self._evict()
        if not session_id:
            return None
        sandbox = self._sandboxes.get(session_id)
        if sandbox is not None:
            sandbox.last_used = self.clock()
            self._sandboxes.move_to_end(session_id)
        return sandbox

    def check_interpret_rate(self, sandbox: Sandbox) -> None:
        now = self.clock()
        calls = sandbox.interpret_calls
        while calls and now - calls[0] > 60:
            calls.popleft()
        if len(calls) >= self.interpret_per_minute:
            raise RateLimited()
        calls.append(now)

    def __len__(self) -> int:
        return len(self._sandboxes)

    def _evict(self) -> None:
        now = self.clock()
        for session_id in [
            sid for sid, box in self._sandboxes.items() if now - box.last_used > self.idle_seconds
        ]:
            self._sandboxes.pop(session_id).session.ledger.close()
