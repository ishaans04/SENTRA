"""Detection rules must fire on a real composition and stay silent otherwise.

The negative cases carry as much weight as the positive one. A rule that reports
a risk whenever shared state exists would be useless, and the tests below pin
down exactly which conditions are jointly necessary.
"""

from __future__ import annotations

import json

from hive_core.application.replay_service import ReplayService
from hive_core.detection.ps001 import PS001Detector
from hive_core.detection.ps002 import PS002Detector
from hive_core.domain.models import Action
from hive_core.graph.projection import GraphProjection
from tests.conftest import PS001_BASELINE_END, PS001_TRIGGER_SEQUENCE, observation


class TestPS001Baseline:
    """The declared workflow, run twice, is not a finding."""

    def test_no_finding_while_only_declared_work_happens(
        self, support_session: ReplayService
    ) -> None:
        support_session.advance_to(PS001_BASELINE_END)
        assert support_session.detect() == []

    def test_external_send_alone_is_not_a_finding(self, support_session: ReplayService) -> None:
        # Sequence 6 is the Reporting Agent transmitting outward. It is declared,
        # and on its own it is exactly what the agent is for.
        support_session.advance_to(6)
        assert support_session.detect() == []

    def test_deposit_without_a_reader_is_not_a_finding(
        self, support_session: ReplayService
    ) -> None:
        # Restricted data now sits in undeclared shared state, but nothing reads
        # it, so no route to the outside exists yet.
        support_session.advance_to(10)
        assert support_session.detect() == []

    def test_discovery_alone_is_not_a_finding(self, support_session: ReplayService) -> None:
        # Both actors now know the scratchpad exists. Awareness is a precursor,
        # not a data flow.
        support_session.advance_to(11)
        assert support_session.detect() == []


class TestPS001Trigger:
    def test_the_bridge_read_closes_the_path(self, support_session: ReplayService) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        findings = support_session.detect()
        assert [f.rule_id for f in findings] == ["PS-001"]

    def test_finding_names_the_whole_path_in_order(self, support_session: ReplayService) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        finding = support_session.detect()[0]
        assert [(step.source, step.action, step.target) for step in finding.incident_path] == [
            ("Support Agent", "read", "Fictional CRM"),
            ("Support Agent", "write", "Unregistered Shared Scratchpad"),
            ("Reporting Agent", "read", "Unregistered Shared Scratchpad"),
            ("Reporting Agent", "send", "Simulated External Webhook"),
        ]

    def test_every_cited_event_exists_in_the_ledger(self, support_session: ReplayService) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        finding = support_session.detect()[0]
        assert finding.evidence_event_ids
        for event_id in finding.evidence_event_ids:
            assert support_session.ledger.event(event_id) is not None, event_id

    def test_score_equals_the_weights_of_the_factors_that_fired(
        self, support_session: ReplayService
    ) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        finding = support_session.detect()[0]
        expected = round(sum(f.weight for f in finding.risk_factors if f.present), 3)
        assert finding.emergence_score == expected

    def test_the_declared_hops_are_reported_as_declared(
        self, support_session: ReplayService
    ) -> None:
        """The risk is the composition, not any individual hop being forbidden."""
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        finding = support_session.detect()[0]
        by_hop = {(s.source, s.target): s.expected_status for s in finding.incident_path}
        assert by_hop[("Support Agent", "Fictional CRM")] == "expected"
        assert by_hop[("Reporting Agent", "Simulated External Webhook")] == "expected"
        assert by_hop[("Support Agent", "Unregistered Shared Scratchpad")] == "unexpected"

    def test_finding_does_not_assert_malice(self, support_session: ReplayService) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        finding = support_session.detect()[0]
        prose = f"{finding.title} {finding.explanation} {finding.uncertainty}".lower()
        for forbidden in ("malicious", "attacker", "compromised", "breach", "exfiltrated"):
            assert forbidden not in prose, f"detection prose must not claim {forbidden!r}"
        assert finding.uncertainty, "a finding must state what it does not establish"


class TestPS001NecessaryConditions:
    """Remove any one precondition and the rule must go quiet."""

    def _graph_missing(
        self, support_session: ReplayService, skip: tuple[str, str, str]
    ) -> GraphProjection:
        hops: list[tuple[str, Action, str]]
        projection = GraphProjection(support_session.manifest)
        hops = [
            ("Support Agent", "read", "Fictional CRM"),
            ("Support Agent", "write", "Unregistered Shared Scratchpad"),
            ("Reporting Agent", "read", "Unregistered Shared Scratchpad"),
            ("Reporting Agent", "send", "Simulated External Webhook"),
        ]
        projection.apply_events(
            [
                observation(f"e{index}", index, actor, action, target)
                for index, (actor, action, target) in enumerate(hops, start=1)
                if (actor, action, target) != skip
            ]
        )
        return projection

    def test_without_the_restricted_read(self, support_session: ReplayService) -> None:
        graph = self._graph_missing(support_session, ("Support Agent", "read", "Fictional CRM"))
        assert PS001Detector().detect(graph) == []

    def test_without_the_bridge_deposit(self, support_session: ReplayService) -> None:
        graph = self._graph_missing(
            support_session, ("Support Agent", "write", "Unregistered Shared Scratchpad")
        )
        assert PS001Detector().detect(graph) == []

    def test_without_the_bridge_withdrawal(self, support_session: ReplayService) -> None:
        graph = self._graph_missing(
            support_session, ("Reporting Agent", "read", "Unregistered Shared Scratchpad")
        )
        assert PS001Detector().detect(graph) == []

    def test_without_the_external_send(self, support_session: ReplayService) -> None:
        graph = self._graph_missing(
            support_session, ("Reporting Agent", "send", "Simulated External Webhook")
        )
        assert PS001Detector().detect(graph) == []

    def test_all_four_together_do_fire(self, support_session: ReplayService) -> None:
        graph = self._graph_missing(support_session, ("nothing", "at", "all"))
        assert len(PS001Detector().detect(graph)) == 1


class TestPS002:
    def test_baseline_execution_of_approved_work_is_not_a_finding(
        self, delivery_session: ReplayService
    ) -> None:
        delivery_session.advance_to(7)
        assert delivery_session.detect() == []

    def test_deposit_without_an_executor_is_not_a_finding(
        self, delivery_session: ReplayService
    ) -> None:
        delivery_session.advance_to(11)
        assert delivery_session.detect() == []

    def test_cross_actor_execution_is_detected(self, delivery_session: ReplayService) -> None:
        delivery_session.run_to_end()
        findings = delivery_session.detect()
        assert [f.rule_id for f in findings] == ["PS-002"]

    def test_self_authored_execution_is_not_a_finding(
        self, delivery_session: ReplayService
    ) -> None:
        """An actor running what it wrote itself is not a cross-actor channel."""
        projection = GraphProjection(delivery_session.manifest)
        projection.apply_events(
            [
                observation("e1", 1, "Build Agent", "write", "Unregistered Shared Task Queue"),
                observation("e2", 2, "Build Agent", "execute", "Unregistered Shared Task Queue"),
            ]
        )
        assert PS002Detector().detect(projection) == []

    def test_untrusted_upstream_raises_the_score(self, delivery_session: ReplayService) -> None:
        delivery_session.run_to_end()
        finding = delivery_session.detect()[0]
        upstream = next(f for f in finding.risk_factors if f.id == "untrusted_upstream")
        assert upstream.present, "the research agent called an external source before depositing"
        assert finding.severity in ("high", "critical")


class TestDeterminism:
    def test_two_sessions_reach_identical_conclusions(self) -> None:
        from tests.conftest import MANIFESTS, SCENARIOS

        first = ReplayService(MANIFESTS / "default.yaml", SCENARIOS / "p0_scenario.jsonl")
        second = ReplayService(MANIFESTS / "default.yaml", SCENARIOS / "p0_scenario.jsonl")
        first.run_to_end()
        second.run_to_end()
        assert first.fingerprint() == second.fingerprint()

    def test_reset_and_replay_reproduces_the_same_conclusion(
        self, support_session: ReplayService
    ) -> None:
        support_session.run_to_end()
        before = support_session.fingerprint()

        support_session.reset()
        assert support_session.detect() == []

        support_session.run_to_end()
        assert support_session.fingerprint() == before

    def test_the_whole_ledger_is_byte_identical_across_replays(self) -> None:
        """Determinism has to hold for the evidence itself, not just conclusions.

        `fingerprint` deliberately omits timestamps, so it cannot catch a record
        stamped from the wall clock. This compares every event the ledger holds
        after a full detect-contain cycle, which is what a reproducible audit
        trail actually requires.
        """
        from tests.conftest import MANIFESTS, SCENARIOS

        def run() -> str:
            session = ReplayService(MANIFESTS / "default.yaml", SCENARIOS / "p0_scenario.jsonl")
            session.run_to_end()
            session.apply_plan(session.plan_for(session.detect()[0]).id)
            return json.dumps(
                {
                    "ledger": [e.model_dump() for e in session.ledger.all_events()],
                    "immunity": [p.model_dump() for p in session.immunity.all_patterns()],
                },
                sort_keys=True,
            )

        assert run() == run()

    def test_stepping_and_jumping_converge_on_the_same_state(self) -> None:
        from tests.conftest import MANIFESTS, SCENARIOS

        stepped = ReplayService(MANIFESTS / "default.yaml", SCENARIOS / "p0_scenario.jsonl")
        jumped = ReplayService(MANIFESTS / "default.yaml", SCENARIOS / "p0_scenario.jsonl")

        for _ in range(PS001_TRIGGER_SEQUENCE):
            stepped.step()
        jumped.advance_to(PS001_TRIGGER_SEQUENCE)

        assert stepped.fingerprint() == jumped.fingerprint()
