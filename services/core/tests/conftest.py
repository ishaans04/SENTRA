"""Shared fixtures.

Every test builds its own session. The core holds replay state in memory, so a
shared session would let one test's containment action decide another test's
result — exactly the hidden coupling these tests exist to rule out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_core.application.replay_service import ReplayService
from hive_core.domain.models import Action, ObservationEvent

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "fixtures"
MANIFESTS = FIXTURES / "manifests"
SCENARIOS = FIXTURES / "scenarios"

#: The sequence at which PS-001's path closes in the canonical scenario: the
#: Reporting Agent's read of the unregistered scratchpad.
PS001_TRIGGER_SEQUENCE = 12

#: The last baseline event, after which nothing should be detected yet.
PS001_BASELINE_END = 8


@pytest.fixture
def support_session() -> ReplayService:
    """A fresh session for the support-estate scenario (PS-001)."""
    return ReplayService(MANIFESTS / "default.yaml", SCENARIOS / "p0_scenario.jsonl")


@pytest.fixture
def delivery_session() -> ReplayService:
    """A fresh session for the delivery-estate scenario (PS-002)."""
    return ReplayService(MANIFESTS / "delivery.yaml", SCENARIOS / "p1_scenario.jsonl")


def observation(
    event_id: str,
    sequence: int,
    actor: str,
    action: Action,
    target: str,
    **context: object,
) -> ObservationEvent:
    """Build a minimal observation for unit tests."""
    return ObservationEvent(
        event_id=event_id,
        sequence=sequence,
        occurred_at=f"2026-09-19T10:{sequence:02d}:00Z",
        actor=actor,
        action=action,
        target=target,
        context=dict(context),
        provenance={"source": "test"},
        result="success",
    )
