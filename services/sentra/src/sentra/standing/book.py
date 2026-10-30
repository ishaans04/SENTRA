"""The book of standing orders, kept across sessions.

Every change appends the whole order as one JSON line; opening the book folds
the file, so the last line for an id wins and the file is its own history.
Without a path the book lives in memory, which is what each visitor's sandbox
and the recorded replay use.
"""

from __future__ import annotations

import json
from pathlib import Path

from sentra.standing.models import StandingOrder


class StandingOrderBook:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._orders: dict[str, StandingOrder] = {}
        if self.path is not None and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    order = StandingOrder(**json.loads(line))
                    self._orders[order.id] = order

    def orders(self) -> list[StandingOrder]:
        return list(self._orders.values())

    def active(self) -> list[StandingOrder]:
        return [o for o in self._orders.values() if o.status == "active"]

    def get(self, order_id: str) -> StandingOrder:
        try:
            return self._orders[order_id]
        except KeyError:
            raise KeyError(f"No standing order {order_id!r}.") from None

    def next_id(self) -> str:
        return f"SO-{len(self._orders) + 1}"

    def put(self, order: StandingOrder) -> None:
        self._orders[order.id] = order.model_copy(deep=True)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(order.model_dump(), sort_keys=True) + "\n")
