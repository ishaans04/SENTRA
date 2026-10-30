"""The book of standing orders, kept across sessions.

A session is handed the book; the sandbox carries a visitor's book into their
next session, and the recorded replay hands the storyline's book to the week
after. Each order is stored as a copy, so a caller holding an order cannot
change the book without putting it back.
"""

from __future__ import annotations

from sentra.standing.models import StandingOrder


class StandingOrderBook:
    def __init__(self) -> None:
        self._orders: dict[str, StandingOrder] = {}

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
