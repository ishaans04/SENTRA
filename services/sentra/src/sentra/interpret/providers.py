"""Model providers behind one interface, with automatic failover.

Free tiers rate-limit, so a provider that errors is skipped for this request
only and the next one is tried. Here the providers themselves are Pydantic AI
agents (see ``chain.py``) and the last link is always the deterministic grammar,
so the chain as a whole never needs the network to produce an answer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class ProviderError(RuntimeError):
    """A provider failed or returned something unusable. The chain tries the next one."""


class Provider[T](Protocol):
    """One way to turn text into a typed result."""

    name: str

    async def run(self, text: str) -> T: ...


class FailoverChain[T]:
    """Try each provider in order; the first that answers wins."""

    def __init__(self, providers: Sequence[Provider[T]]) -> None:
        if not providers:
            raise ValueError("FailoverChain needs at least one provider")
        self.providers = list(providers)
        self.last_used: str | None = None
        self.failures: list[str] = []

    async def run(self, text: str) -> T:
        self.failures = []
        for provider in self.providers:
            try:
                result = await provider.run(text)
            except ProviderError as exc:
                self.failures.append(f"{provider.name}: {exc}")
                continue
            self.last_used = provider.name
            return result
        raise ProviderError("all providers failed -> " + " | ".join(self.failures))
