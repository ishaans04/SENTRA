"""The fictional world behind the tool servers.

One ``World`` per session: customer records, the report store, the shared
scratchpad and the webhook's delivery log. Every mutable item keeps its full
version history, because recovery has to compare what an agent produced with
what is there now before it undoes anything (INV-8).

Tool servers learn who is calling from ``CALLER``, a context variable the
gateway sets from the connection before it forwards a call. Tool arguments
never carry identity, so an agent cannot claim to be someone else (INV-3).
"""

from __future__ import annotations

from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

#: The actor on whose behalf the current tool call runs. Set by the gateway.
CALLER: ContextVar[str] = ContextVar("sentra_caller", default="unknown")


@dataclass
class Version:
    version: int
    content: str | None
    writer: str


@dataclass
class Item:
    """A mutable, versioned record in a resource."""

    id: str
    resource: str
    history: list[Version] = field(default_factory=list)

    @property
    def version(self) -> int:
        return self.history[-1].version if self.history else 0

    @property
    def content(self) -> str | None:
        return self.history[-1].content if self.history else None

    @property
    def writer(self) -> str | None:
        return self.history[-1].writer if self.history else None

    def content_at(self, version: int) -> str | None:
        for entry in self.history:
            if entry.version == version:
                return entry.content
        return None


#: Fictional customer records. Restricted: only Support's declared work reads them.
_CUSTOMERS: dict[str, dict[str, str]] = {
    "cust-1042": {
        "id": "cust-1042",
        "name": "Fictional Customer 1042",
        "email": "customer1042@example.invalid",
        "issue": "Billing address out of date.",
    },
}


@dataclass
class World:
    items: dict[str, Item] = field(default_factory=dict)
    customers: dict[str, dict[str, str]] = field(default_factory=dict)
    #: (grantee, resource) pairs. The writer of a scratchpad note can always read it.
    grants: set[tuple[str, str]] = field(default_factory=set)
    deliveries: list[dict[str, Any]] = field(default_factory=list)
    counters: Counter[str] = field(default_factory=Counter)

    @classmethod
    def seed(cls) -> World:
        return cls(customers={key: dict(value) for key, value in _CUSTOMERS.items()})

    def write(self, item_id: str, resource: str, content: str | None, writer: str) -> Item:
        """Append a new version of *item_id* and return the item."""
        item = self.items.setdefault(item_id, Item(id=item_id, resource=resource))
        item.history.append(Version(item.version + 1, content, writer))
        return item

    def items_in(self, resource: str) -> list[Item]:
        return [item for item in self.items.values() if item.resource == resource]

    def can_read(self, actor: str, resource: str) -> bool:
        if (actor, resource) in self.grants:
            return True
        return any(item.writer == actor for item in self.items_in(resource))

    def count(self, tool: str) -> int:
        return self.counters[tool]
