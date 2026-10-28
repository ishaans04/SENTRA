"""Manifest loading and invariant evaluation."""

from __future__ import annotations

from typing import Any, cast

import pytest
import yaml

from hive_core.application.replay_service import ReplayService
from hive_core.policy.engine import ManifestError, PolicyEngine
from tests.conftest import MANIFESTS, PS001_TRIGGER_SEQUENCE


def _write(tmp_path: Any, manifest: dict[str, Any]) -> str:
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return str(path)


def _valid() -> dict[str, Any]:
    return {
        "version": "test/v1",
        "zones": {"work": {"trust": "internal"}},
        "nodes": [
            {
                "id": "Agent",
                "kind": "agent",
                "label": "Agent",
                "zone": "work",
                "data_classification": "internal",
                "registration": "expected",
            },
            {
                "id": "Store",
                "kind": "store",
                "label": "Store",
                "zone": "work",
                "data_classification": "internal",
                "registration": "expected",
            },
        ],
        "allowed_relationships": [{"source": "Agent", "action": "read", "target": "Store"}],
        "invariants": [],
        "control_capabilities": [],
    }


class TestManifestLoading:
    def test_shipped_manifests_load(self) -> None:
        engine = PolicyEngine()
        for name in ("default", "delivery"):
            manifest = engine.load_manifest(MANIFESTS / f"{name}.yaml")
            assert manifest.version
            assert manifest.nodes

    def test_a_valid_manifest_round_trips(self, tmp_path) -> None:
        manifest = PolicyEngine().load_manifest(_write(tmp_path, _valid()))
        assert manifest.allows("Agent", "read", "Store") is True
        assert manifest.allows("Agent", "write", "Store") is False

    def test_a_missing_file_is_reported_clearly(self, tmp_path) -> None:
        with pytest.raises(ManifestError, match="No manifest"):
            PolicyEngine().load_manifest(tmp_path / "absent.yaml")

    def test_a_relationship_naming_an_undeclared_node_is_rejected(self, tmp_path) -> None:
        broken = _valid()
        broken["allowed_relationships"].append(
            {"source": "Ghost", "action": "read", "target": "Store"}
        )
        with pytest.raises(ManifestError, match="undeclared node 'Ghost'"):
            PolicyEngine().load_manifest(_write(tmp_path, broken))

    def test_a_capability_naming_an_undeclared_node_is_rejected(self, tmp_path) -> None:
        """Otherwise it looks viable in planning and does nothing when applied."""
        broken = _valid()
        broken["control_capabilities"] = [
            {
                "id": "cap",
                "type": "block_edge",
                "label": "Block a ghost",
                "source": "Agent",
                "action": "read",
                "target": "Ghost Store",
                "reversible": True,
                "cost": 1,
            }
        ]
        with pytest.raises(ManifestError, match="undeclared node 'Ghost Store'"):
            PolicyEngine().load_manifest(_write(tmp_path, broken))

    def test_a_block_edge_without_a_source_is_rejected(self, tmp_path) -> None:
        broken = _valid()
        broken["control_capabilities"] = [
            {
                "id": "cap",
                "type": "block_edge",
                "label": "Incomplete",
                "target": "Store",
                "reversible": True,
                "cost": 1,
            }
        ]
        with pytest.raises(ManifestError, match="must declare"):
            PolicyEngine().load_manifest(_write(tmp_path, broken))

    def test_a_node_in_an_undeclared_zone_is_rejected(self, tmp_path) -> None:
        broken = _valid()
        broken["nodes"][0]["zone"] = "nowhere"
        with pytest.raises(ManifestError, match="no entry under 'zones'"):
            PolicyEngine().load_manifest(_write(tmp_path, broken))


class TestInvariants:
    def test_the_baseline_violates_nothing(self, support_session: ReplayService) -> None:
        support_session.advance_to(8)
        results = support_session.policy.check_invariants(support_session.graph)
        assert results, "the manifest declares an invariant"
        assert all(result["violated"] is False for result in results)

    def test_the_emergent_path_violates_the_invariant(self, support_session: ReplayService) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        results = support_session.policy.check_invariants(support_session.graph)
        violated = [r for r in results if r["violated"]]
        assert len(violated) == 1
        invariant = cast(dict[str, str], violated[0]["invariant"])
        assert invariant["id"] == "no-restricted-egress-via-unregistered-state"

    def test_a_violation_carries_a_concrete_witness_path(
        self, support_session: ReplayService
    ) -> None:
        support_session.advance_to(PS001_TRIGGER_SEQUENCE)
        violated = next(
            r
            for r in support_session.policy.check_invariants(support_session.graph)
            if r["violated"]
        )
        witness = cast(list[str], violated["witness_path"])
        assert witness[0] == "Fictional CRM"
        assert witness[-1] == "Simulated External Webhook"
        assert "Unregistered Shared Scratchpad" in witness

    def test_containment_clears_the_violation(self, support_session: ReplayService) -> None:
        support_session.run_to_end()
        plan = support_session.plan_for(support_session.detect()[0])
        support_session.apply_plan(plan.id)

        results = support_session.policy.check_invariants(support_session.graph)
        assert all(result["violated"] is False for result in results)

    def test_the_rule_and_the_invariant_agree(self, support_session: ReplayService) -> None:
        """Two independent checks of the same claim should not disagree."""
        for sequence in range(1, 13):
            support_session.reset()
            support_session.advance_to(sequence)
            rule_fired = any(f.rule_id == "PS-001" for f in support_session.detect())
            invariant_violated = any(
                r["violated"]
                for r in support_session.policy.check_invariants(support_session.graph)
            )
            assert rule_fired == invariant_violated, f"disagreement at sequence {sequence}"
