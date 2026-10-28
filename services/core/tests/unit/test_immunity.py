"""Immunity memory: recorded automatically, promoted only by a person."""

from __future__ import annotations

import pytest

from hive_core.domain.models import Finding
from hive_core.immunity.registry import ImmunityRegistry, LifecycleError

#: Timestamps come from the replay position, so tests supply one explicitly.
STAMP = "2026-09-19T10:31:00Z"


def _finding(rule_id: str = "PS-001") -> Finding:
    return Finding(
        id=f"finding-{rule_id.lower()}",
        rule_id=rule_id,  # type: ignore[arg-type]
        title="A composed capability the architecture forbids",
        status="contained",
        severity="high",
        manifest_version="test/v1",
        detected_at_sequence=12,
        policy_basis="basis",
        evidence_event_ids=["e1", "e2"],
        explanation="explanation",
    )


@pytest.fixture
def registry() -> ImmunityRegistry:
    return ImmunityRegistry()


class TestRecording:
    def test_a_contained_finding_becomes_a_draft(self, registry: ImmunityRegistry) -> None:
        pattern = registry.record_from_finding(_finding(), STAMP)
        assert pattern.lifecycle == "draft"
        assert pattern.promoted_at is None

    def test_the_record_is_stamped_from_the_replay_not_the_clock(
        self, registry: ImmunityRegistry
    ) -> None:
        assert registry.record_from_finding(_finding(), STAMP).created_at == STAMP

    def test_recording_the_same_finding_twice_does_not_duplicate(
        self, registry: ImmunityRegistry
    ) -> None:
        first = registry.record_from_finding(_finding(), STAMP)
        second = registry.record_from_finding(_finding(), STAMP)
        assert first.id == second.id
        assert len(registry.all_patterns()) == 1

    def test_each_rule_records_its_own_preconditions(self, registry: ImmunityRegistry) -> None:
        ps001 = registry.record_from_finding(_finding("PS-001"), STAMP)
        ps002 = registry.record_from_finding(_finding("PS-002"), STAMP)
        assert ps001.abstract_preconditions != ps002.abstract_preconditions
        assert ps001.recommended_control_class != ps002.recommended_control_class

    def test_evidence_is_carried_from_the_finding(self, registry: ImmunityRegistry) -> None:
        pattern = registry.record_from_finding(_finding(), STAMP)
        assert pattern.evidence_basis == ["e1", "e2"]


class TestLifecycle:
    def test_draft_promotes_to_shadow(self, registry: ImmunityRegistry) -> None:
        pattern = registry.record_from_finding(_finding(), STAMP)
        promoted = registry.promote(pattern.id, "shadow", STAMP)
        assert promoted.lifecycle == "shadow"
        assert promoted.promoted_at is not None

    def test_shadow_promotes_to_active(self, registry: ImmunityRegistry) -> None:
        pattern = registry.record_from_finding(_finding(), STAMP)
        registry.promote(pattern.id, "shadow", STAMP)
        assert registry.promote(pattern.id, "active", STAMP).lifecycle == "active"

    def test_draft_cannot_jump_straight_to_active(self, registry: ImmunityRegistry) -> None:
        """A pattern must be observed in shadow before it is allowed to act."""
        pattern = registry.record_from_finding(_finding(), STAMP)
        with pytest.raises(LifecycleError, match="Cannot move"):
            registry.promote(pattern.id, "active", STAMP)

    def test_promotion_is_reversible(self, registry: ImmunityRegistry) -> None:
        pattern = registry.record_from_finding(_finding(), STAMP)
        registry.promote(pattern.id, "shadow", STAMP)
        registry.promote(pattern.id, "active", STAMP)
        assert registry.promote(pattern.id, "shadow", STAMP).lifecycle == "shadow"
        assert registry.promote(pattern.id, "draft", STAMP).lifecycle == "draft"

    def test_an_unknown_pattern_is_an_error(self, registry: ImmunityRegistry) -> None:
        with pytest.raises(LifecycleError, match="No immunity pattern"):
            registry.promote("immunity-nope", "shadow", STAMP)

    def test_an_unknown_stage_is_an_error(self, registry: ImmunityRegistry) -> None:
        pattern = registry.record_from_finding(_finding(), STAMP)
        with pytest.raises(LifecycleError):
            registry.promote(pattern.id, "enforcing", STAMP)

    def test_clear_empties_the_registry(self, registry: ImmunityRegistry) -> None:
        registry.record_from_finding(_finding(), STAMP)
        registry.clear()
        assert registry.all_patterns() == []
