"""Scenario discovery and replay-session lifecycle.

The console can switch between scenarios, and each one runs against its own
architecture manifest. This registry owns that mapping and keeps one live
:class:`ReplayService` per scenario, so switching away and back does not silently
discard where the operator had got to.

Sessions are per-process and in-memory by design. HIVE's local-first posture
means there is no database to configure and nothing to clean up: restart the
service and every session returns to its initial state.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

from hive_core.application.replay_service import ReplayService
from hive_core.lab.scenarios import ScenarioError, ScenarioLoader


class ScenarioRegistry:
    """Resolve scenario ids to manifests and hold their live sessions."""

    def __init__(self, scenarios_dir: str | Path, manifests_dir: str | Path) -> None:
        self.scenarios_dir = Path(scenarios_dir)
        self.manifests_dir = Path(manifests_dir)
        self._loader = ScenarioLoader(self.scenarios_dir)
        self._sessions: dict[str, ReplayService] = {}
        self._lock = RLock()

    # ------------------------------------------------------------------

    def catalogue(self) -> list[dict[str, Any]]:
        """Describe every available scenario without instantiating a session."""
        return [
            {
                "id": descriptor.id,
                "name": descriptor.name,
                "manifest_id": descriptor.manifest_id,
                "rule_id": descriptor.rule_id,
                "summary": descriptor.summary,
                "event_count": descriptor.event_count,
            }
            for descriptor in self._loader.available()
        ]

    def default_scenario_id(self) -> str:
        catalogue = self.catalogue()
        if not catalogue:
            raise ScenarioError(f"No scenario fixtures found in {self.scenarios_dir}.")
        return str(catalogue[0]["id"])

    def session(self, scenario_id: str) -> ReplayService:
        """The live session for *scenario_id*, creating it on first use."""
        with self._lock:
            existing = self._sessions.get(scenario_id)
            if existing is not None:
                return existing

            scenario_path = self.scenarios_dir / f"{scenario_id}.jsonl"
            if not scenario_path.exists():
                raise ScenarioError(f"No scenario fixture named {scenario_id!r}.")

            manifest_id = self._loader.manifest_id_for(scenario_id)
            manifest_path = self.manifests_dir / f"{manifest_id}.yaml"
            if not manifest_path.exists():
                raise ScenarioError(
                    f"Scenario {scenario_id!r} declares manifest {manifest_id!r}, "
                    f"which does not exist at {manifest_path}."
                )

            session = ReplayService(manifest_path, scenario_path)
            self._sessions[scenario_id] = session
            return session

    def reset_all(self) -> None:
        """Return every live session to its initial state."""
        with self._lock:
            for session in self._sessions.values():
                session.reset()
