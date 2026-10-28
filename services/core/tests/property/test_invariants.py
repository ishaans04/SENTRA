"""Properties that must hold for any event stream, not just the scripted ones.

Scenario fixtures prove the demo works. These prove the underlying reasoning is
not tuned to it: the generators below build arbitrary interaction streams over
the canonical node set, including sequences no scenario contains.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hive_core.containment.planner import ContainmentPlanner, apply_control
from hive_core.detection.base import Detector
from hive_core.detection.ps001 import PS001Detector
from hive_core.detection.ps002 import PS002Detector
from hive_core.domain.models import ObservationEvent
from hive_core.graph.projection import GraphProjection
from hive_core.policy.engine import PolicyEngine
from tests.conftest import MANIFESTS

_MANIFEST = PolicyEngine().load_manifest(MANIFESTS / "default.yaml")
_NODES = [node.id for node in _MANIFEST.nodes]
_ACTIONS = ["read", "write", "send", "call", "discover", "message", "execute"]

_SETTINGS = settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@st.composite
def event_streams(draw: st.DrawFn) -> list[ObservationEvent]:
    """Arbitrary well-formed observation streams over the canonical estate."""
    count = draw(st.integers(min_value=0, max_value=14))
    events = []
    for index in range(count):
        actor = draw(st.sampled_from(_NODES))
        target = draw(st.sampled_from([n for n in _NODES if n != actor]))
        events.append(
            ObservationEvent(
                event_id=f"p{index}",
                sequence=index + 1,
                occurred_at=f"2026-09-19T10:{index:02d}:00Z",
                actor=actor,
                action=draw(st.sampled_from(_ACTIONS)),
                target=target,
                context={},
                provenance={},
                result="success",
            )
        )
    return events


def _detectors() -> list[Detector]:
    return [PS001Detector(), PS002Detector()]


def _projection(events: list[ObservationEvent]) -> GraphProjection:
    projection = GraphProjection(_MANIFEST)
    projection.apply_events(events)
    return projection


class TestProjectionProperties:
    @_SETTINGS
    @given(events=event_streams())
    def test_the_edge_map_and_the_graph_always_agree(self, events: list[ObservationEvent]) -> None:
        projection = _projection(events)
        from_graph = {(u, v, k) for u, v, k in projection.graph.edges(keys=True)}
        from_map = {(e.source, e.target, e.action) for e in projection.edges}
        assert from_graph == from_map

    @_SETTINGS
    @given(events=event_streams())
    def test_applying_a_stream_twice_changes_nothing(self, events: list[ObservationEvent]) -> None:
        once = _projection(events)
        twice = _projection(events)
        twice.apply_events(events)
        assert {e.key for e in once.edges} == {e.key for e in twice.edges}

    @_SETTINGS
    @given(events=event_streams())
    def test_reset_always_returns_to_the_declared_baseline(
        self, events: list[ObservationEvent]
    ) -> None:
        projection = _projection(events)
        projection.reset()
        assert projection.edges == []
        assert projection.graph.number_of_nodes() == len(_MANIFEST.nodes)

    @_SETTINGS
    @given(events=event_streams())
    def test_a_copy_is_never_entangled_with_its_original(
        self, events: list[ObservationEvent]
    ) -> None:
        projection = _projection(events)
        before = {e.key for e in projection.edges}
        clone = projection.copy()
        for edge in list(clone.edges):
            clone.remove_edge(edge.source, edge.target, edge.action)
        assert {e.key for e in projection.edges} == before


class TestDetectionProperties:
    @_SETTINGS
    @given(events=event_streams())
    def test_detection_is_pure(self, events: list[ObservationEvent]) -> None:
        """Running the rules must not change what the rules will next conclude."""
        projection = _projection(events)
        first = [
            f.model_dump() for d in (PS001Detector(), PS002Detector()) for f in d.detect(projection)
        ]
        second = [
            f.model_dump() for d in (PS001Detector(), PS002Detector()) for f in d.detect(projection)
        ]
        assert first == second

    @_SETTINGS
    @given(events=event_streams())
    def test_every_cited_event_was_actually_observed(self, events: list[ObservationEvent]) -> None:
        projection = _projection(events)
        observed = {event.event_id for event in events}
        for detector in _detectors():
            for finding in detector.detect(projection):
                assert set(finding.evidence_event_ids) <= observed

    @_SETTINGS
    @given(events=event_streams())
    def test_a_finding_always_names_a_complete_path(self, events: list[ObservationEvent]) -> None:
        projection = _projection(events)
        for detector in _detectors():
            for finding in detector.detect(projection):
                assert finding.incident_path
                for step in finding.incident_path:
                    assert projection.edge(step.source, step.target, step.action) is not None

    @_SETTINGS
    @given(events=event_streams())
    def test_the_score_is_always_reconstructible_from_the_factors(
        self, events: list[ObservationEvent]
    ) -> None:
        projection = _projection(events)
        for detector in _detectors():
            for finding in detector.detect(projection):
                expected = round(sum(f.weight for f in finding.risk_factors if f.present), 3)
                assert finding.emergence_score == expected
                assert 0.0 <= finding.emergence_score <= 1.0

    @_SETTINGS
    @given(events=event_streams())
    def test_an_empty_estate_is_never_a_finding(self, events: list[ObservationEvent]) -> None:
        projection = GraphProjection(_MANIFEST)
        assert PS001Detector().detect(projection) == []
        assert PS002Detector().detect(projection) == []


class TestContainmentProperties:
    @_SETTINGS
    @given(events=event_streams())
    def test_the_recommendation_always_does_what_the_plan_claims(
        self, events: list[ObservationEvent]
    ) -> None:
        """The core guarantee: a viable candidate really is viable."""
        projection = _projection(events)
        detectors: list[Detector] = [PS001Detector(), PS002Detector()]
        planner = ContainmentPlanner(_MANIFEST, detectors)

        for detector in detectors:
            for finding in detector.detect(projection):
                plan = planner.plan(finding, projection)
                if plan.recommended_capability_id is None:
                    continue
                capability = next(
                    c
                    for c in _MANIFEST.control_capabilities
                    if c.id == plan.recommended_capability_id
                )
                applied = projection.copy()
                apply_control(applied, capability)

                assert detector.detect(applied) == [], "the path must actually be gone"

                before = {e.key for e in projection.edges if e.expected_status == "expected"}
                after = {e.key for e in applied.edges if e.expected_status == "expected"}
                assert before == after, "declared work must actually survive"

    @_SETTINGS
    @given(events=event_streams())
    def test_containment_never_recommends_an_unregistered_action(
        self, events: list[ObservationEvent]
    ) -> None:
        projection = _projection(events)
        detectors: list[Detector] = [PS001Detector(), PS002Detector()]
        planner = ContainmentPlanner(_MANIFEST, detectors)
        registered = {c.id for c in _MANIFEST.control_capabilities}

        for detector in detectors:
            for finding in detector.detect(projection):
                plan = planner.plan(finding, projection)
                assert {c.capability_id for c in plan.candidates} <= registered
                if plan.recommended_capability_id is not None:
                    assert plan.recommended_capability_id in registered

    @_SETTINGS
    @given(events=event_streams())
    def test_the_recommendation_is_always_the_cheapest_viable_one(
        self, events: list[ObservationEvent]
    ) -> None:
        projection = _projection(events)
        detectors: list[Detector] = [PS001Detector(), PS002Detector()]
        planner = ContainmentPlanner(_MANIFEST, detectors)

        for detector in detectors:
            for finding in detector.detect(projection):
                plan = planner.plan(finding, projection)
                viable = [c for c in plan.candidates if c.viable]
                if not viable:
                    assert plan.recommended_capability_id is None
                    continue
                cheapest = min(c.cost for c in viable)
                chosen = next(
                    c for c in plan.candidates if c.capability_id == plan.recommended_capability_id
                )
                assert chosen.cost == cheapest


class TestControlProperties:
    @_SETTINGS
    @given(
        events=event_streams(),
        capability_index=st.integers(min_value=0, max_value=4),
    )
    def test_applying_a_control_is_idempotent(
        self, events: list[ObservationEvent], capability_index: int
    ) -> None:
        projection = _projection(events)
        capability = _MANIFEST.control_capabilities[capability_index]

        once = projection.copy()
        apply_control(once, capability)
        twice = once.copy()
        apply_control(twice, capability)

        assert {e.key for e in once.edges} == {e.key for e in twice.edges}

    @_SETTINGS
    @given(
        events=event_streams(),
        capability_index=st.integers(min_value=0, max_value=4),
    )
    def test_a_control_only_ever_removes_relationships(
        self, events: list[ObservationEvent], capability_index: int
    ) -> None:
        projection = _projection(events)
        before = {e.key for e in projection.edges}

        applied = projection.copy()
        apply_control(applied, _MANIFEST.control_capabilities[capability_index])
        after = {e.key for e in applied.edges}

        assert after <= before
        assert applied.graph.number_of_nodes() == projection.graph.number_of_nodes()
