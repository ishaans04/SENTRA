"""The API exercised the way the console uses it.

The centrepiece is the full operator journey: reset, replay, detect, inspect,
contain, verify. It is written as one ordered test because that sequence is the
product claim, and a judge should be able to read it as the specification.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from hive_core.main import app

SCENARIO = "p0_scenario"
BASE = f"/api/v1/replays/{SCENARIO}"


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A client whose scenario sessions start clean.

    The service holds replay state in memory across requests, so every test
    resets first. Without that, one test's containment action would decide the
    next test's result.
    """
    with TestClient(app) as test_client:
        test_client.post(f"{BASE}/reset")
        test_client.post("/api/v1/replays/p1_scenario/reset")
        yield test_client


# ---------------------------------------------------------------------------
# Service metadata
# ---------------------------------------------------------------------------


class TestService:
    def test_health_reports_the_operating_mode(self, client: TestClient) -> None:
        body = client.get("/api/v1/health").json()
        assert body["status"] == "ok"
        assert body["mode"] == "local-simulation"

    def test_health_states_the_safety_posture(self, client: TestClient) -> None:
        safety = client.get("/api/v1/health").json()["safety"]
        assert safety == {
            "network_egress": False,
            "real_data": False,
            "enforcement": "simulated",
        }

    def test_scenarios_are_listed_with_the_rule_they_exercise(self, client: TestClient) -> None:
        scenarios = client.get("/api/v1/scenarios").json()["scenarios"]
        by_id = {s["id"]: s for s in scenarios}
        assert by_id["p0_scenario"]["rule_id"] == "PS-001"
        assert by_id["p1_scenario"]["rule_id"] == "PS-002"
        assert by_id["p1_scenario"]["manifest_id"] == "delivery"
        assert all(s["summary"] for s in scenarios)

    def test_an_unknown_scenario_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/replays/nope/state").status_code == 404


# ---------------------------------------------------------------------------
# The operator journey
# ---------------------------------------------------------------------------


class TestOperatorJourney:
    def test_the_full_detect_contain_verify_flow(self, client: TestClient) -> None:
        # 1. A fresh replay shows the declared architecture and nothing else.
        state = client.get(f"{BASE}/state").json()
        assert state["cursor"] == 0
        assert state["graph"]["edges"] == []
        assert len(state["graph"]["nodes"]) == 8
        assert client.get(f"{BASE}/findings").json()["findings"] == []

        # 2. The baseline workflow runs. Still nothing to report.
        client.post(f"{BASE}/advance", params={"to_sequence": 8})
        assert client.get(f"{BASE}/findings").json()["findings"] == []

        # 3. The rest of the scenario plays out and the path closes.
        client.post(f"{BASE}/run")
        envelope = client.get(f"{BASE}/findings").json()
        assert len(envelope["findings"]) == 1

        finding = envelope["findings"][0]
        assert finding["rule_id"] == "PS-001"
        assert finding["status"] == "open"
        assert len(finding["incident_path"]) == 4
        assert finding["evidence_event_ids"]
        assert finding["uncertainty"]

        # 4. The plan compares every registered control and picks the cheapest
        #    that works without breaking declared work.
        plan = envelope["plans"][0]
        assert plan["state"] == "proposed"
        assert len(plan["candidates"]) == 5
        assert plan["recommended_capability_id"] == "block-support-scratchpad-write"

        # 5. Applying it severs one relationship and verifies the result.
        applied = client.post(f"{BASE}/plans/{plan['id']}/apply").json()
        verification = applied["plan"]["verification"]
        assert applied["plan"]["state"] == "verified"
        assert verification["unsafe_path_removed"] is True
        assert verification["workflow_preserved"] is True
        assert verification["broken_declared_relationships"] == []

        # 6. The finding is gone and the declared workflow is intact.
        assert applied["findings"]["findings"] == []
        surviving = {edge["id"] for edge in applied["state"]["graph"]["edges"]}
        assert "Support Agent--write-->Unregistered Shared Scratchpad" not in surviving
        assert "Support Agent--read-->Fictional CRM" in surviving
        assert "Reporting Agent--send-->Simulated External Webhook" in surviving

        # 7. Containment is recorded as evidence, and remembered as a draft.
        assert "block-support-scratchpad-write" in applied["state"]["applied_controls"]
        patterns = client.get(f"{BASE}/immunity").json()["patterns"]
        assert len(patterns) == 1
        assert patterns[0]["lifecycle"] == "draft"

    def test_the_second_estate_tells_the_same_story_with_other_names(
        self, client: TestClient
    ) -> None:
        base = "/api/v1/replays/p1_scenario"
        client.post(f"{base}/run")

        envelope = client.get(f"{base}/findings").json()
        assert envelope["findings"][0]["rule_id"] == "PS-002"

        plan = envelope["plans"][0]
        applied = client.post(f"{base}/plans/{plan['id']}/apply").json()
        assert applied["plan"]["state"] == "verified"
        assert applied["findings"]["findings"] == []


# ---------------------------------------------------------------------------
# Replay controls
# ---------------------------------------------------------------------------


class TestReplayControls:
    def test_stepping_advances_exactly_one_event(self, client: TestClient) -> None:
        body = client.post(f"{BASE}/advance").json()
        assert len(body["applied_events"]) == 1
        assert body["cursor"] == 1
        assert body["at_end"] is False

    def test_running_to_the_end_reports_it(self, client: TestClient) -> None:
        body = client.post(f"{BASE}/run").json()
        assert body["at_end"] is True
        assert body["cursor"] == 12

    def test_reset_returns_to_the_start(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        client.post(f"{BASE}/reset")
        state = client.get(f"{BASE}/state").json()
        assert state["cursor"] == 0
        assert state["graph"]["edges"] == []

    def test_reset_undoes_a_containment(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        plan = client.get(f"{BASE}/findings").json()["plans"][0]
        client.post(f"{BASE}/plans/{plan['id']}/apply")

        client.post(f"{BASE}/reset")
        client.post(f"{BASE}/run")
        assert len(client.get(f"{BASE}/findings").json()["findings"]) == 1

    def test_scenarios_do_not_share_state(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        other = client.get("/api/v1/replays/p1_scenario/state").json()
        assert other["cursor"] == 0


class TestReadsDoNotMutate:
    def test_repeated_reads_return_identical_payloads(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        first = client.get(f"{BASE}/findings").json()
        second = client.get(f"{BASE}/findings").json()
        assert first == second

    def test_reading_findings_does_not_move_the_cursor(self, client: TestClient) -> None:
        client.post(f"{BASE}/advance", params={"to_sequence": 5})
        before = client.get(f"{BASE}/state").json()["cursor"]
        client.get(f"{BASE}/findings")
        client.get(f"{BASE}/architecture")
        assert client.get(f"{BASE}/state").json()["cursor"] == before

    def test_reading_findings_issues_no_control(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        for _ in range(3):
            client.get(f"{BASE}/findings")
        assert client.get(f"{BASE}/state").json()["applied_controls"] == []


# ---------------------------------------------------------------------------
# Detail routes
# ---------------------------------------------------------------------------


class TestFindingDetail:
    def test_a_known_finding_returns_its_plan(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        body = client.get(f"{BASE}/findings/finding-ps001").json()
        assert body["finding"]["rule_id"] == "PS-001"
        assert body["plan"]["finding_id"] == "finding-ps001"

    def test_an_unknown_finding_is_a_404(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        assert client.get(f"{BASE}/findings/finding-nope").status_code == 404

    def test_architecture_returns_what_detection_is_measured_against(
        self, client: TestClient
    ) -> None:
        body = client.get(f"{BASE}/architecture").json()
        assert body["version"] == "support-estate/v1"
        assert len(body["nodes"]) == 8
        assert len(body["allowed_relationships"]) == 6
        assert len(body["control_capabilities"]) == 5
        assert body["invariants"][0]["status"] == "prohibited"

    def test_state_reports_invariant_evaluation(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        invariants = client.get(f"{BASE}/state").json()["invariants"]
        assert any(entry["violated"] for entry in invariants)
        violated = next(entry for entry in invariants if entry["violated"])
        assert violated["witness_path"][0] == "Fictional CRM"


class TestContainmentErrors:
    def test_applying_an_unknown_plan_is_a_404(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        assert client.post(f"{BASE}/plans/plan-nope/apply").status_code == 404

    def test_applying_twice_is_idempotent(self, client: TestClient) -> None:
        client.post(f"{BASE}/run")
        plan = client.get(f"{BASE}/findings").json()["plans"][0]
        first = client.post(f"{BASE}/plans/{plan['id']}/apply").json()
        second = client.post(f"{BASE}/plans/{plan['id']}/apply").json()
        assert first["plan"]["state"] == second["plan"]["state"] == "verified"
        assert len(second["state"]["applied_controls"]) == 1


class TestImmunityLifecycle:
    def _contain(self, client: TestClient) -> str:
        client.post(f"{BASE}/run")
        plan = client.get(f"{BASE}/findings").json()["plans"][0]
        client.post(f"{BASE}/plans/{plan['id']}/apply")
        return str(client.get(f"{BASE}/immunity").json()["patterns"][0]["id"])

    def test_a_pattern_can_be_promoted_one_stage_at_a_time(self, client: TestClient) -> None:
        pattern_id = self._contain(client)
        body = client.post(f"{BASE}/immunity/{pattern_id}/promote", json={"to": "shadow"}).json()
        assert body["pattern"]["lifecycle"] == "shadow"
        assert body["pattern"]["promoted_at"]

    def test_skipping_shadow_is_refused(self, client: TestClient) -> None:
        pattern_id = self._contain(client)
        response = client.post(f"{BASE}/immunity/{pattern_id}/promote", json={"to": "active"})
        assert response.status_code == 400
        assert "Cannot move" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Swarm Lab
# ---------------------------------------------------------------------------


class TestLab:
    def test_options_describe_every_valid_value(self, client: TestClient) -> None:
        options = client.get("/api/v1/lab/options").json()
        assert "unregistered_shared_resource" in options["perturbation"]
        assert options["population"]["max"] >= options["population"]["min"]

    def test_a_run_returns_real_findings_and_a_real_plan(self, client: TestClient) -> None:
        body = client.post(
            "/api/v1/lab/simulate",
            json={
                "population": 24,
                "shared_memory": "enabled",
                "external_access": "broad",
                "perturbation": "unregistered_shared_resource",
            },
        ).json()
        assert body["outcome"] == "risk_detected"
        assert body["findings"][0]["rule_id"] == "PS-001"
        assert body["plans"][0]["recommended_capability_id"]
        assert body["interpretation"]

    def test_a_safe_configuration_says_so_and_says_why(self, client: TestClient) -> None:
        body = client.post(
            "/api/v1/lab/simulate",
            json={"population": 24, "shared_memory": "off", "external_access": "none"},
        ).json()
        assert body["outcome"] == "no_composition_found"
        assert body["findings"] == []
        assert body["interpretation"]

    def test_an_out_of_range_population_is_rejected(self, client: TestClient) -> None:
        assert client.post("/api/v1/lab/simulate", json={"population": 100000}).status_code == 422
