"""Containment is where the project's central claim either holds or does not.

Three things have to be true together: the recommendation removes the path, it
leaves the declared workflow running, and applying it produces the state the
planner predicted. The last one is the easiest to get wrong and the least
visible, so it is tested directly.
"""

from __future__ import annotations

import pytest

from hive_core.application.replay_service import ReplayService
from hive_core.containment.planner import apply_control
from tests.conftest import PS001_TRIGGER_SEQUENCE

#: Controls are stamped from the replay position rather than the wall clock.
STAMP = "2026-09-19T10:31:00Z"


@pytest.fixture
def contained(support_session: ReplayService) -> ReplayService:
    support_session.run_to_end()
    return support_session


class TestCandidateEvaluation:
    def test_every_registered_capability_is_evaluated(self, contained: ReplayService) -> None:
        plan = contained.plan_for(contained.detect()[0])
        assert len(plan.candidates) == len(contained.manifest.control_capabilities) == 5

    def test_the_cheapest_working_candidate_is_recommended(self, contained: ReplayService) -> None:
        plan = contained.plan_for(contained.detect()[0])
        assert plan.recommended_capability_id == "block-support-scratchpad-write"

    def test_three_candidates_work_and_two_are_rejected(self, contained: ReplayService) -> None:
        plan = contained.plan_for(contained.detect()[0])
        viable = {c.capability_id for c in plan.candidates if c.viable}
        assert viable == {
            "block-support-scratchpad-write",
            "block-reporting-scratchpad-read",
            "quarantine-shared-scratchpad",
        }

    def test_a_candidate_that_severs_declared_work_is_rejected_with_a_reason(
        self, contained: ReplayService
    ) -> None:
        plan = contained.plan_for(contained.detect()[0])
        by_id = {c.capability_id: c for c in plan.candidates}

        crm_block = by_id["block-support-crm-read"]
        assert crm_block.removes_unsafe_path is True, "it does break the path"
        assert crm_block.viable is False, "but it stops support doing its job"
        assert "Support Agent--read-->Fictional CRM" in crm_block.broken_expected_relationships
        assert "declared relationships" in crm_block.rejection_reason

        send_block = by_id["block-reporting-external-send"]
        assert send_block.viable is False
        assert (
            "Reporting Agent--send-->Simulated External Webhook"
            in send_block.broken_expected_relationships
        )

    def test_rejected_candidates_are_still_shown(self, contained: ReplayService) -> None:
        """An operator should see what was considered, not only what was chosen."""
        plan = contained.plan_for(contained.detect()[0])
        assert sum(1 for c in plan.candidates if not c.viable) == 2

    def test_recommendation_is_stable_across_sessions(self) -> None:
        from tests.conftest import MANIFESTS, SCENARIOS

        picks = set()
        for _ in range(3):
            session = ReplayService(MANIFESTS / "default.yaml", SCENARIOS / "p0_scenario.jsonl")
            session.run_to_end()
            picks.add(session.plan_for(session.detect()[0]).recommended_capability_id)
        assert len(picks) == 1


class TestSimulationMatchesReality:
    """What the planner predicts must be what the control actually does."""

    @pytest.mark.parametrize(
        "capability_id",
        [
            "block-support-scratchpad-write",
            "block-reporting-scratchpad-read",
            "quarantine-shared-scratchpad",
            "block-reporting-external-send",
            "block-support-crm-read",
        ],
    )
    def test_predicted_outcome_matches_applied_outcome(
        self, contained: ReplayService, capability_id: str
    ) -> None:
        plan = contained.plan_for(contained.detect()[0])
        predicted = next(c for c in plan.candidates if c.capability_id == capability_id)
        capability = next(
            c for c in contained.manifest.control_capabilities if c.id == capability_id
        )

        applied = contained.graph.copy()
        apply_control(applied, capability)

        from hive_core.detection.ps001 import PS001Detector

        actually_removed = not PS001Detector().detect(applied)
        assert actually_removed == predicted.removes_unsafe_path

        surviving = {e.key for e in applied.edges if e.expected_status == "expected"}
        before = {e.key for e in contained.graph.edges if e.expected_status == "expected"}
        assert sorted(before - surviving) == predicted.broken_expected_relationships


class TestApplyAndVerify:
    def test_applying_the_recommendation_clears_the_finding(self, contained: ReplayService) -> None:
        plan = contained.plan_for(contained.detect()[0])
        result = contained.apply_plan(plan.id)

        assert result.state == "verified"
        assert result.verification["unsafe_path_removed"] is True
        assert contained.detect() == []

    def test_the_declared_workflow_survives_containment(self, contained: ReplayService) -> None:
        plan = contained.plan_for(contained.detect()[0])
        result = contained.apply_plan(plan.id)

        assert result.verification["broken_declared_relationships"] == []
        assert result.verification["workflow_preserved"] is True

        surviving = {e.key for e in contained.graph.edges}
        for relationship in [
            "Support Agent--read-->Fictional CRM",
            "Support Agent--write-->Approved Ticket Store",
            "Analytics Agent--read-->Approved Ticket Store",
            "Analytics Agent--write-->Internal Report Store",
            "Reporting Agent--read-->Internal Report Store",
            "Reporting Agent--send-->Simulated External Webhook",
        ]:
            assert relationship in surviving, f"{relationship} was disrupted"

    def test_only_the_named_relationship_is_severed(self, contained: ReplayService) -> None:
        before = {e.key for e in contained.graph.edges}
        plan = contained.plan_for(contained.detect()[0])
        contained.apply_plan(plan.id)
        after = {e.key for e in contained.graph.edges}

        assert before - after == {"Support Agent--write-->Unregistered Shared Scratchpad"}

    def test_the_agents_discovery_of_the_scratchpad_is_left_alone(
        self, contained: ReplayService
    ) -> None:
        """Containment is scoped to an action, not to a pair of nodes."""
        plan = contained.plan_for(contained.detect()[0])
        contained.apply_plan(plan.id)
        assert (
            contained.graph.edge("Support Agent", "Unregistered Shared Scratchpad", "discover")
            is not None
        )

    def test_the_control_is_recorded_in_the_ledger_as_evidence(
        self, contained: ReplayService
    ) -> None:
        plan = contained.plan_for(contained.detect()[0])
        result = contained.apply_plan(plan.id)

        for event_id in result.verification["control_event_ids"]:
            event = contained.ledger.event(event_id)
            assert event is not None
            assert event.action == "block"
            assert event.context["simulated"] is True
            assert event.context["capability_id"] == "block-support-scratchpad-write"

    def test_applying_twice_is_idempotent(self, contained: ReplayService) -> None:
        plan = contained.plan_for(contained.detect()[0])
        first = contained.apply_plan(plan.id)
        second = contained.apply_plan(plan.id)

        assert first.state == second.state == "verified"
        assert len([e for e in contained.ledger.all_events() if e.action == "block"]) == 1

    def test_an_unknown_plan_is_an_error_not_an_arbitrary_control(
        self, contained: ReplayService
    ) -> None:
        with pytest.raises(KeyError):
            contained.apply_plan("plan-does-not-exist")
        assert [e for e in contained.ledger.all_events() if e.action == "block"] == []

    def test_reset_undoes_containment_completely(self, contained: ReplayService) -> None:
        plan = contained.plan_for(contained.detect()[0])
        contained.apply_plan(plan.id)
        contained.reset()

        assert contained.detect() == []
        assert contained.graph.applied_controls == []
        assert [e for e in contained.ledger.all_events() if e.action == "block"] == []

        contained.run_to_end()
        assert [f.rule_id for f in contained.detect()] == ["PS-001"]


class TestDeliveryEstate:
    """The same machinery, a different architecture."""

    def test_ps002_is_contained_and_verified(self, delivery_session: ReplayService) -> None:
        delivery_session.run_to_end()
        plan = delivery_session.plan_for(delivery_session.detect()[0])

        assert plan.recommended_capability_id == "block-research-queue-write"

        result = delivery_session.apply_plan(plan.id)
        assert result.state == "verified"
        assert delivery_session.detect() == []
        assert result.verification["broken_declared_relationships"] == []

    def test_the_build_agent_can_still_execute_approved_work(
        self, delivery_session: ReplayService
    ) -> None:
        delivery_session.run_to_end()
        plan = delivery_session.plan_for(delivery_session.detect()[0])
        delivery_session.apply_plan(plan.id)

        assert (
            delivery_session.graph.edge("Build Agent", "Approved Job Store", "execute") is not None
        )


class TestImmunityRecord:
    def test_containment_records_a_draft_pattern(self, contained: ReplayService) -> None:
        assert contained.immunity.all_patterns() == []

        plan = contained.plan_for(contained.detect()[0])
        contained.apply_plan(plan.id)

        patterns = contained.immunity.all_patterns()
        assert len(patterns) == 1
        assert patterns[0].lifecycle == "draft", "a pattern is never auto-activated"
        assert patterns[0].rule_id == "PS-001"

    def test_the_pattern_is_abstract_not_a_list_of_node_names(
        self, contained: ReplayService
    ) -> None:
        plan = contained.plan_for(contained.detect()[0])
        contained.apply_plan(plan.id)
        pattern = contained.immunity.all_patterns()[0]

        joined = " ".join(pattern.abstract_preconditions)
        assert joined, "a pattern must record its preconditions"
        for fixture_name in ("Support Agent", "Reporting Agent", "Fictional CRM", "Scratchpad"):
            assert fixture_name not in joined, "memory must be portable to another estate"


class TestNoFindingNoPlan:
    def test_the_baseline_produces_no_plan(self, support_session: ReplayService) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE - 1)
        envelope = support_session.findings_envelope()
        assert envelope["findings"] == []
        assert envelope["plans"] == []
