"""Record the engine's output at every replay position.

The hosted console has no backend. Rather than mock one — which would mean the
public demo shows numbers no engine produced — this module runs the real
:class:`ReplayService` across every cursor position of every scenario, applies
each containment plan, and writes the results as static JSON the console loads
directly.

Everything in the snapshot therefore came out of the same code path a local run
exercises. The console labels the source ``recorded`` so nobody mistakes it for
a live service.

Regenerate with::

    uv run python -m hive_core.snapshot
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hive_core.application.replay_service import ReplayService
from hive_core.application.scenario_registry import ScenarioRegistry
from hive_core.lab.swarm import SwarmConfig, SwarmSimulator

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURES = _REPO_ROOT / "fixtures"

SNAPSHOT_DIR = _REPO_ROOT / "apps" / "console" / "public" / "demo"

#: The lab axes the recording varies. Connectivity and delegation are held at
#: their default because they change the texture of a synthetic population
#: without changing whether a composition forms; the console says so rather than
#: offering controls that would silently do nothing.
_LAB_POPULATIONS = (12, 24, 48, 96)
_LAB_SHARED_MEMORY = ("off", "limited", "enabled")
_LAB_EXTERNAL = ("none", "limited", "broad")
_LAB_PERTURBATIONS = (
    "none",
    "unregistered_shared_resource",
    "cross_agent_execution",
    "delegation_cascade",
    "new_external_endpoint",
)
_LAB_HELD: tuple[str, ...] = ("connectivity", "delegation")


def lab_key(config: SwarmConfig) -> str:
    return "__".join(
        str(part)
        for part in (
            config.population,
            config.shared_memory,
            config.external_access,
            config.perturbation,
        )
    )


def _architecture(session: ReplayService) -> dict[str, Any]:
    manifest = session.manifest
    return {
        "version": manifest.version,
        "zones": manifest.zones,
        "nodes": [node.model_dump() for node in manifest.nodes],
        "allowed_relationships": [r.model_dump() for r in manifest.allowed_relationships],
        "invariants": [i.model_dump() for i in manifest.invariants],
        "control_capabilities": [c.model_dump() for c in manifest.control_capabilities],
    }


def record_scenario(manifest_path: Path, scenario_path: Path) -> dict[str, Any]:
    """Replay a scenario end to end, capturing every intermediate state."""
    session = ReplayService(manifest_path, scenario_path)

    steps: list[dict[str, Any]] = []
    cursors = [0, *[event.sequence for event in session.ledger.all_events()]]
    for cursor in cursors:
        session.reset()
        if cursor:
            session.advance_to(cursor)
        steps.append(
            {
                "cursor": cursor,
                "state": session.state(),
                "findings": session.findings_envelope(),
            }
        )

    # Then the contained state: run to the end, apply the recommendation, and
    # capture what verification actually established.
    session.reset()
    session.run_to_end()
    findings = session.detect()
    contained: dict[str, Any]
    if findings:
        plan = session.plan_for(findings[0])
        applied = session.apply_plan(plan.id)
        contained = {
            "plan": applied.model_dump(),
            "state": session.state(),
            "findings": session.findings_envelope(),
            "immunity": [p.model_dump() for p in session.immunity.all_patterns()],
        }
    else:  # pragma: no cover - every shipped scenario produces a finding
        contained = {
            "plan": None,
            "state": session.state(),
            "findings": session.findings_envelope(),
            "immunity": [],
        }

    return {"architecture": _architecture(session), "steps": steps, "contained": contained}


def record_lab() -> dict[str, dict[str, Any]]:
    """Run the lab across the recorded parameter grid."""
    simulator = SwarmSimulator()
    results: dict[str, dict[str, Any]] = {}
    for population in _LAB_POPULATIONS:
        for shared_memory in _LAB_SHARED_MEMORY:
            for external in _LAB_EXTERNAL:
                for perturbation in _LAB_PERTURBATIONS:
                    config = SwarmConfig(
                        population=population,
                        shared_memory=shared_memory,  # type: ignore[arg-type]
                        external_access=external,  # type: ignore[arg-type]
                        perturbation=perturbation,  # type: ignore[arg-type]
                    )
                    results[lab_key(config)] = simulator.run(config)
    return results


def write_snapshot(target: Path = SNAPSHOT_DIR) -> Path:
    """Generate the complete snapshot under *target*."""
    registry = ScenarioRegistry(_FIXTURES / "scenarios", _FIXTURES / "manifests")
    catalogue = registry.catalogue()

    target.mkdir(parents=True, exist_ok=True)
    (target / "lab").mkdir(parents=True, exist_ok=True)

    for descriptor in catalogue:
        scenario_id = str(descriptor["id"])
        recorded = record_scenario(
            _FIXTURES / "manifests" / f"{descriptor['manifest_id']}.yaml",
            _FIXTURES / "scenarios" / f"{scenario_id}.jsonl",
        )
        _write(target / f"{scenario_id}.json", recorded)

    lab = record_lab()
    for key, result in lab.items():
        _write(target / "lab" / f"{key}.json", result)

    _write(
        target / "index.json",
        {
            # Deliberately no timestamp. The snapshot is a pure function of the
            # fixtures and the engine, and CI compares it byte-for-byte against
            # a fresh run — a wall clock in here would make that check
            # meaningless and would quietly contradict the determinism claim.
            "engine_version": "1.0.0",
            "scenarios": catalogue,
            "lab": {
                "held": list(_LAB_HELD),
                "populations": list(_LAB_POPULATIONS),
                "keys": sorted(lab),
            },
        },
    )
    return target


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - developer entry point
    written = write_snapshot()
    total = sum(f.stat().st_size for f in written.rglob("*.json"))
    print(f"Wrote {written} ({total / 1024:.0f} KB)")
