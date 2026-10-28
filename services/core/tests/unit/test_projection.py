"""The graph projection must represent what the ledger actually said.

The tests that matter here are the ones covering parallel actions between one
pair of nodes. Modelling those with a simple digraph loses information silently,
and every downstream claim about containment depends on not losing it.
"""

from __future__ import annotations

import pytest

from hive_core.domain.models import ArchitectureManifest, Node, Relationship
from hive_core.graph.projection import GraphProjection
from tests.conftest import observation


def _manifest() -> ArchitectureManifest:
    return ArchitectureManifest(
        version="test/v1",
        zones={
            "work": {"trust": "internal"},
            "shared": {"trust": "untrusted"},
            "outside": {"trust": "external"},
        },
        nodes=[
            Node(
                id="Agent A",
                kind="agent",
                label="Agent A",
                zone="work",
                data_classification="internal",
                registration="expected",
            ),
            Node(
                id="Agent B",
                kind="agent",
                label="Agent B",
                zone="work",
                data_classification="internal",
                registration="expected",
            ),
            Node(
                id="Records",
                kind="datasource",
                label="Records",
                zone="work",
                data_classification="restricted",
                registration="expected",
            ),
            Node(
                id="Scratch",
                kind="store",
                label="Scratch",
                zone="shared",
                data_classification="internal",
                registration="unregistered",
            ),
            Node(
                id="Outside",
                kind="destination",
                label="Outside",
                zone="outside",
                data_classification="public",
                registration="expected",
            ),
        ],
        allowed_relationships=[
            Relationship(source="Agent A", action="read", target="Records"),
        ],
    )


@pytest.fixture
def projection() -> GraphProjection:
    return GraphProjection(_manifest())


class TestSeeding:
    def test_declared_nodes_exist_before_any_event(self, projection: GraphProjection) -> None:
        assert projection.graph.number_of_nodes() == 5
        assert projection.edges == []

    def test_zone_trust_is_attached_from_the_manifest(self, projection: GraphProjection) -> None:
        assert projection.graph.nodes["Scratch"]["trust"] == "untrusted"
        assert projection.graph.nodes["Outside"]["trust"] == "external"
        assert projection.graph.nodes["Agent A"]["trust"] == "internal"

    def test_undeclared_node_is_marked_rather_than_assumed_benign(
        self, projection: GraphProjection
    ) -> None:
        projection.apply_events([observation("e1", 1, "Agent A", "write", "Mystery Store")])
        node = projection.graph.nodes["Mystery Store"]
        assert node["declared"] is False
        assert node["registration"] == "unknown"


class TestParallelActions:
    """Two actions between the same pair are two relationships, not one."""

    def test_both_actions_survive(self, projection: GraphProjection) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "discover", "Scratch"),
                observation("e2", 2, "Agent A", "write", "Scratch"),
            ]
        )
        actions = sorted(edge.action for edge in projection.edges)
        assert actions == ["discover", "write"]

    def test_blocking_one_action_leaves_the_other(self, projection: GraphProjection) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "discover", "Scratch"),
                observation("e2", 2, "Agent A", "write", "Scratch"),
            ]
        )
        assert projection.remove_edge("Agent A", "Scratch", "write") is True

        remaining = [edge.action for edge in projection.edges]
        assert remaining == ["discover"]
        assert projection.edge("Agent A", "Scratch", "write") is None
        assert projection.edge("Agent A", "Scratch", "discover") is not None

    def test_edge_map_and_graph_never_disagree(self, projection: GraphProjection) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "discover", "Scratch"),
                observation("e2", 2, "Agent A", "write", "Scratch"),
                observation("e3", 3, "Agent B", "read", "Scratch"),
            ]
        )
        projection.remove_edge("Agent A", "Scratch", "write")

        from_graph = {(u, v, k) for u, v, k in projection.graph.edges(keys=True)}
        from_map = {(e.source, e.target, e.action) for e in projection.edges}
        assert from_graph == from_map


class TestObservationAccounting:
    def test_repeat_observation_increments_count_and_records_evidence(
        self, projection: GraphProjection
    ) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "read", "Records"),
                observation("e2", 2, "Agent A", "read", "Records"),
            ]
        )
        edge = projection.edge("Agent A", "Records", "read")
        assert edge is not None
        assert edge.observation_count == 2
        assert edge.evidence_event_ids == ["e1", "e2"]

    def test_replaying_the_same_event_is_idempotent(self, projection: GraphProjection) -> None:
        event = observation("e1", 1, "Agent A", "read", "Records")
        projection.apply_events([event, event])
        edge = projection.edge("Agent A", "Records", "read")
        assert edge is not None
        assert edge.observation_count == 1

    def test_expected_status_comes_from_the_manifest(self, projection: GraphProjection) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "read", "Records"),
                observation("e2", 2, "Agent A", "write", "Scratch"),
            ]
        )
        declared = projection.edge("Agent A", "Records", "read")
        emergent = projection.edge("Agent A", "Scratch", "write")
        assert declared is not None and declared.expected_status == "expected"
        assert emergent is not None and emergent.expected_status == "unexpected"


class TestControlEvents:
    def test_block_event_severs_exactly_the_named_relationship(
        self, projection: GraphProjection
    ) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "discover", "Scratch"),
                observation("e2", 2, "Agent A", "write", "Scratch"),
                observation(
                    "c1",
                    99,
                    "HIVE Control Plane",
                    "block",
                    "Scratch",
                    source="Agent A",
                    blocked_action="write",
                    capability_id="cap-1",
                    control_type="block_edge",
                ),
            ]
        )
        assert [e.action for e in projection.edges] == ["discover"]
        assert projection.applied_controls == ["cap-1"]

    def test_quarantine_removes_every_incident_relationship(
        self, projection: GraphProjection
    ) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "write", "Scratch"),
                observation("e2", 2, "Agent B", "read", "Scratch"),
                observation("e3", 3, "Agent A", "read", "Records"),
                observation(
                    "c1",
                    99,
                    "HIVE Control Plane",
                    "block",
                    "Scratch",
                    capability_id="cap-q",
                    control_type="quarantine_node",
                ),
            ]
        )
        assert [e.key for e in projection.edges] == ["Agent A--read-->Records"]
        assert projection.graph.has_node("Scratch"), "quarantine isolates, it does not delete"

    def test_malformed_block_event_is_rejected_rather_than_ignored(
        self, projection: GraphProjection
    ) -> None:
        with pytest.raises(ValueError, match="must carry"):
            projection.apply_events(
                [observation("c1", 99, "HIVE Control Plane", "block", "Scratch")]
            )


class TestDataFlowOrientation:
    """Reads carry content against the recorded arrow."""

    def test_interaction_graph_alone_cannot_see_the_route(
        self, projection: GraphProjection
    ) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "read", "Records"),
                observation("e2", 2, "Agent A", "write", "Scratch"),
                observation("e3", 3, "Agent B", "read", "Scratch"),
                observation("e4", 4, "Agent B", "send", "Outside"),
            ]
        )
        assert projection.has_path("Records", "Outside") is False
        assert projection.data_reaches("Records", "Outside") is True

    def test_severing_the_deposit_closes_the_data_route(self, projection: GraphProjection) -> None:
        projection.apply_events(
            [
                observation("e1", 1, "Agent A", "read", "Records"),
                observation("e2", 2, "Agent A", "write", "Scratch"),
                observation("e3", 3, "Agent B", "read", "Scratch"),
                observation("e4", 4, "Agent B", "send", "Outside"),
            ]
        )
        projection.remove_edge("Agent A", "Scratch", "write")
        assert projection.data_reaches("Records", "Outside") is False


class TestLifecycle:
    def test_reset_returns_to_the_seeded_baseline(self, projection: GraphProjection) -> None:
        projection.apply_events([observation("e1", 1, "Agent A", "write", "Scratch")])
        projection.reset()
        assert projection.edges == []
        assert projection.graph.number_of_nodes() == 5

    def test_copy_is_independent_of_the_original(self, projection: GraphProjection) -> None:
        projection.apply_events([observation("e1", 1, "Agent A", "write", "Scratch")])
        clone = projection.copy()
        clone.remove_edge("Agent A", "Scratch", "write")

        assert clone.edges == []
        assert len(projection.edges) == 1, "mutating a simulation must not touch the live graph"
