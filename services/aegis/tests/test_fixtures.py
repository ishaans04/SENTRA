"""The reporting estate, checked by HIVE itself before any gateway exists."""

from __future__ import annotations

from pathlib import Path

import yaml
from hive_core.application.replay_service import ReplayService
from hive_core.policy.engine import PolicyEngine


def test_manifest_loads_in_hive(fixtures_dir: Path) -> None:
    manifest = PolicyEngine().load_manifest(fixtures_dir / "manifest.yaml")
    ids = {node.id for node in manifest.nodes}
    assert {"support-agent", "reporting-agent", "crm", "scratchpad", "webhook"} <= ids
    assert len(manifest.control_capabilities) == 4


def test_hand_written_hops_raise_ps001(fixtures_dir: Path) -> None:
    service = ReplayService(fixtures_dir / "manifest.yaml", fixtures_dir / "hops.jsonl")
    service.run_to_end()
    findings = service.detect()
    assert [f.rule_id for f in findings] == ["PS-001"]
    assert len(findings[0].incident_path) == 4
    plan = service.plan_for(findings[0])
    assert plan.recommended_capability_id == "deny-reporting-scratchpad-read"
    rejected = {c.capability_id for c in plan.candidates if not c.viable}
    assert rejected == {"block-reporting-webhook-send", "deny-support-crm-read"}


def test_every_tool_names_a_manifest_resource(fixtures_dir: Path) -> None:
    manifest = PolicyEngine().load_manifest(fixtures_dir / "manifest.yaml")
    ids = {node.id for node in manifest.nodes}
    tools = yaml.safe_load((fixtures_dir / "tools.yaml").read_text(encoding="utf-8"))["tools"]
    assert {tool["resource"] for tool in tools} <= ids
