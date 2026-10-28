"""Swarm Lab must be an experiment, not an animation.

The tests that matter are the ones proving the lab runs the production rules and
that its answers change for the right reasons — including answering "no risk"
when the configuration genuinely composes nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from hive_core.lab.swarm import SwarmConfig, SwarmSimulator


@pytest.fixture
def simulator() -> SwarmSimulator:
    return SwarmSimulator()


class TestDeterminism:
    def test_the_same_configuration_yields_the_same_result(self, simulator: SwarmSimulator) -> None:
        config = SwarmConfig(population=30, external_access="limited")
        assert simulator.run(config) == simulator.run(config)

    def test_different_configurations_yield_different_seeds(self) -> None:
        assert SwarmConfig(population=10).seed() != SwarmConfig(population=11).seed()

    def test_the_seed_is_reported_so_a_run_can_be_reproduced(
        self, simulator: SwarmSimulator
    ) -> None:
        result = simulator.run(SwarmConfig())
        assert result["determinism"]["seed"] == SwarmConfig().seed()


class TestRealAnalysis:
    def test_a_finding_carries_the_same_structure_as_a_live_one(
        self, simulator: SwarmSimulator
    ) -> None:
        result = simulator.run(
            SwarmConfig(
                population=20,
                shared_memory="enabled",
                external_access="broad",
                perturbation="unregistered_shared_resource",
            )
        )
        assert result["outcome"] == "risk_detected"
        finding = result["findings"][0]
        assert finding["rule_id"] == "PS-001"
        assert finding["incident_path"], "the lab reports the same evidenced path"
        assert finding["risk_factors"]
        assert finding["uncertainty"]

    def test_the_planner_runs_and_recommends_a_registered_control(
        self, simulator: SwarmSimulator
    ) -> None:
        result = simulator.run(
            SwarmConfig(
                population=20,
                shared_memory="enabled",
                external_access="broad",
                perturbation="unregistered_shared_resource",
            )
        )
        plan = result["plans"][0]
        assert plan["recommended_capability_id"] is not None
        assert plan["candidates"], "candidates are evaluated, not assumed"

    def test_cross_agent_execution_triggers_the_second_rule(
        self, simulator: SwarmSimulator
    ) -> None:
        result = simulator.run(
            SwarmConfig(
                population=20,
                shared_memory="enabled",
                perturbation="cross_agent_execution",
            )
        )
        assert "PS-002" in {f["rule_id"] for f in result["findings"]}


class TestNegativeResults:
    """Answering 'no' for a stated reason is the lab's most useful output."""

    def test_no_shared_state_composes_nothing(self, simulator: SwarmSimulator) -> None:
        result = simulator.run(
            SwarmConfig(shared_memory="off", perturbation="unregistered_shared_resource")
        )
        assert result["outcome"] == "no_composition_found"
        assert "undeclared shared state" in result["interpretation"]

    def test_shared_state_without_egress_composes_nothing(self, simulator: SwarmSimulator) -> None:
        result = simulator.run(
            SwarmConfig(
                population=20,
                shared_memory="enabled",
                external_access="none",
                perturbation="unregistered_shared_resource",
            )
        )
        assert result["outcome"] == "no_composition_found"
        assert result["findings"] == []

    def test_no_perturbation_composes_nothing(self, simulator: SwarmSimulator) -> None:
        result = simulator.run(SwarmConfig(perturbation="none", external_access="broad"))
        assert result["outcome"] == "no_composition_found"

    def test_granting_egress_is_what_closes_the_path(self, simulator: SwarmSimulator) -> None:
        shared: dict[str, Any] = {
            "population": 20,
            "shared_memory": "enabled",
            "perturbation": "unregistered_shared_resource",
        }
        closed = simulator.run(SwarmConfig(**shared, external_access="none"))
        opened = simulator.run(SwarmConfig(**shared, external_access="broad"))
        assert closed["outcome"] == "no_composition_found"
        assert opened["outcome"] == "risk_detected"


class TestBounds:
    @pytest.mark.parametrize("population", [1, 3, 50, 200, 5000])
    def test_population_is_clamped_to_a_workable_range(
        self, simulator: SwarmSimulator, population: int
    ) -> None:
        result = simulator.run(SwarmConfig(population=population))
        reported = result["config"]["population"]
        assert SwarmSimulator.MIN_POPULATION <= reported <= SwarmSimulator.MAX_POPULATION

    def test_the_reported_population_matches_the_synthesised_one(
        self, simulator: SwarmSimulator
    ) -> None:
        result = simulator.run(SwarmConfig(population=17))
        assert result["population"]["agents"] == 17

    def test_every_perturbation_runs_without_error(self, simulator: SwarmSimulator) -> None:
        for perturbation in (
            "none",
            "unregistered_shared_resource",
            "cross_agent_execution",
            "delegation_cascade",
            "new_external_endpoint",
        ):
            result = simulator.run(SwarmConfig(perturbation=perturbation))
            assert result["interpretation"]
