"""Scenario fixtures: deterministic, fictional event streams.

A scenario is a JSON Lines file. Each line is one observation. Loading validates
every line through the ingest boundary, so a fixture cannot introduce an event
shape the platform would refuse from a real collector.

Duplicate ``event_id`` values are rejected at load time. The ledger deduplicates
by id, which means a fixture with repeated ids silently loses events and the
scenario quietly stops matching its own description. Failing loudly here is the
difference between a demo that is reproducible and one that only looks it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hive_core.domain.models import ObservationEvent
from hive_core.ingest.validator import EventValidationError, EventValidator
from hive_core.ledger.repository import LedgerRepository


class ScenarioError(ValueError):
    """Raised when a scenario fixture cannot be loaded."""


@dataclass(frozen=True)
class ScenarioDescriptor:
    """Everything the console needs to offer a scenario without loading it."""

    id: str
    name: str
    manifest_id: str
    rule_id: str
    summary: str
    event_count: int


#: Which manifest each scenario is written against, and how to describe it.
#: Kept here rather than inside the fixture so a fixture stays pure event data.
_CATALOGUE: dict[str, tuple[str, str, str, str]] = {
    "p0_scenario": (
        "The unintended export path",
        "default",
        "PS-001",
        "Three support agents work exactly as designed. An undeclared scratchpad "
        "appears between two of them, and an ordinary read completes a route from "
        "restricted customer data to an external destination.",
    ),
    "p1_scenario": (
        "The unreviewed instruction channel",
        "delivery",
        "PS-002",
        "A research agent files work through an undeclared queue instead of the "
        "review path. The build agent executes what it finds there, turning a "
        "granted capability into an unreviewed channel from outside the estate.",
    ),
}


class ScenarioLoader:
    """Read and validate scenario fixtures from a directory."""

    def __init__(self, scenarios_dir: str | Path) -> None:
        self.directory = Path(scenarios_dir)

    def available(self) -> list[ScenarioDescriptor]:
        """Describe every scenario on disk, cheapest-first by event count."""
        descriptors: list[ScenarioDescriptor] = []
        for path in sorted(self.directory.glob("*.jsonl")):
            name, manifest_id, rule_id, summary = _CATALOGUE.get(
                path.stem,
                (path.stem.replace("_", " ").title(), "default", "PS-001", ""),
            )
            descriptors.append(
                ScenarioDescriptor(
                    id=path.stem,
                    name=name,
                    manifest_id=manifest_id,
                    rule_id=rule_id,
                    summary=summary,
                    event_count=sum(
                        1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
                    ),
                )
            )
        return descriptors

    def manifest_id_for(self, scenario_id: str) -> str:
        return _CATALOGUE.get(scenario_id, ("", "default", "", ""))[1]

    def load(self, scenario_id: str) -> list[ObservationEvent]:
        """Load, validate, and order the events of *scenario_id*."""
        path = self.directory / f"{scenario_id}.jsonl"
        if not path.exists():
            raise ScenarioError(f"No scenario fixture named {scenario_id!r}.")

        events: list[ObservationEvent] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ScenarioError(
                    f"{path.name} line {line_number}: invalid JSON — {exc}"
                ) from exc
            try:
                events.append(EventValidator.validate(raw))
            except EventValidationError as exc:
                raise ScenarioError(f"{path.name} line {line_number}: {exc}") from exc

        duplicates = LedgerRepository.duplicate_event_ids(events)
        if duplicates:
            raise ScenarioError(
                f"{path.name} repeats event ids {', '.join(duplicates)}. The ledger "
                "deduplicates by id, so these events would be dropped and the "
                "scenario would not replay as written."
            )

        repeated = LedgerRepository.duplicate_sequences(events)
        if repeated:
            raise ScenarioError(
                f"{path.name} repeats sequence numbers "
                f"{', '.join(str(sequence) for sequence in repeated)}. Stepping one event and "
                "advancing to a sequence would then disagree about how far the replay moved."
            )

        return sorted(events, key=lambda event: event.sequence)
