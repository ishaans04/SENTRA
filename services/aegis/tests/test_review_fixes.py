"""Regression tests for the findings of the whole-build review."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from aegis.api.app import create_app
from aegis.api.sessions import SessionManager
from aegis.conditions.predicates import NoUndeclaredPath
from aegis.decisions.graph import DecisionGraph
from aegis.decisions.models import ConditionProposal, DecisionProposal
from aegis.ledger import SessionLedger
from aegis.scenario import Session

STORY_RECOVERY = (
    "Stop this reporting run, remove its scratchpad access, and rebuild the report from "
    "approved summaries. Keep the support work."
)


@pytest.fixture
def manager(fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch) -> SessionManager:
    monkeypatch.setenv("AEGIS_INTERPRETER", "off")
    return SessionManager(fixtures_dir, cap=3, idle_minutes=30, interpret_per_minute=4)


def _client(manager: SessionManager) -> httpx.AsyncClient:
    app = create_app(manager)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://haegis.local")


async def _to_beat_8(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    for _ in range(7):
        await client.post("/api/story/step")


# -- 1: a spoken confirm runs the plan on screen ----------------------------------


async def test_new_draft_supersedes_and_spoken_confirm_runs_the_newest(
    manager: SessionManager,
) -> None:
    client = _client(manager)
    await _to_beat_8(client)
    first = (
        await client.post(
            "/api/recovery/interpret",
            json={"text": "Stop this reporting run. Keep the support work."},
        )
    ).json()
    second = (await client.post("/api/recovery/interpret", json={"text": STORY_RECOVERY})).json()
    confirmed = (await client.post("/api/recovery/interpret", json={"text": "Yes, run it."})).json()
    assert confirmed["id"] == second["id"]
    state = (await client.get("/api/state")).json()
    statuses = {p["id"]: p["status"] for p in state["plans"]}
    assert statuses[first["id"]] == "abandoned"


# -- 2, 3, 4: sandbox and stream lifecycle ------------------------------------------


async def test_events_for_a_missing_session_is_a_404_envelope(manager: SessionManager) -> None:
    response = await _client(manager).get("/api/events", params={"follow": "false"})
    assert response.status_code == 404
    assert response.json()["error"] == "no_session"


async def test_last_event_id_from_an_older_session_is_ignored(manager: SessionManager) -> None:
    client = _client(manager)
    await client.post("/api/session")
    response = await client.get(
        "/api/events", params={"follow": "false"}, headers={"Last-Event-ID": "999"}
    )
    assert "id: 1\n" in response.text


async def test_replacing_a_session_ends_its_open_streams(fixtures_dir: Path) -> None:
    session = Session("s-old", fixtures_dir)
    queue = session.ledger.subscribe()
    session.ledger.close()
    assert queue.get_nowait() is None
    assert session.ledger.subscriber_count == 0


async def test_too_many_streams_on_one_session_are_refused(manager: SessionManager) -> None:
    client = _client(manager)
    await client.post("/api/session")
    sandbox = manager.get(client.cookies["haegis_session"])
    assert sandbox is not None
    for _ in range(4):
        sandbox.session.ledger.subscribe()
    response = await client.get("/api/events", params={"follow": "false"})
    assert response.status_code == 429


# -- 5: a plan whose approval was withdrawn fails plainly ---------------------------


async def test_confirm_after_the_approval_was_withdrawn_is_409_not_500(
    manager: SessionManager,
) -> None:
    client = _client(manager)
    await _to_beat_8(client)
    plan = (await client.post("/api/recovery/interpret", json={"text": STORY_RECOVERY})).json()
    await client.post("/api/decisions/D-1/withdraw")
    response = await client.post(f"/api/recovery/{plan['id']}/confirm")
    assert response.status_code == 409
    assert "D-1" in response.json()["message"]


async def test_a_step_that_throws_fails_the_plan_instead_of_wedging_it(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegis.recovery.plan import Rebuild

    session = Session("s-throw", fixtures_dir)
    await session.run_to(8)
    plan = session.recovery.draft(
        [Rebuild(decision_id="D-1", sources=["report_store/approved_summaries"])],
        text="",
        interpreted_by="grammar",
    )

    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("renew exploded")

    monkeypatch.setattr(session.decisions, "renew", boom)
    await session.recovery.confirm(plan.id)
    assert session.recovery.get(plan.id).status == "failed"
    assert [e.kind for e in session.ledger.events()][-1] == "recovery.step_failed"


# -- 6, 7: the storyline never wedges and never confirms for the operator -----------


async def test_play_with_a_broken_storyline_is_409(manager: SessionManager) -> None:
    client = _client(manager)
    await client.post("/api/session")
    await client.post("/api/story/step")
    await client.post("/api/story/step")
    await client.post("/api/decisions/D-1/withdraw")
    response = await client.post("/api/story/play")
    assert response.status_code == 409
    beat = (await client.get("/api/state")).json()["beat"]
    response = await client.post("/api/story/step")
    assert response.status_code == 409
    assert (await client.get("/api/state")).json()["beat"] == beat


async def test_step_does_not_confirm_the_operators_pending_approval(
    manager: SessionManager,
) -> None:
    client = _client(manager)
    await client.post("/api/session")
    await client.post("/api/decisions/interpret", json={"text": "Approve reporting"})
    await client.post("/api/story/step")
    response = await client.post("/api/story/step")
    assert response.status_code == 409
    assert "read-back" in response.json()["message"]
    state = (await client.get("/api/state")).json()
    assert [d["status"] for d in state["decisions"]] == ["active", "proposed"]


async def test_step_does_not_confirm_the_operators_pending_plan(manager: SessionManager) -> None:
    client = _client(manager)
    await _to_beat_8(client)
    await client.post("/api/recovery/interpret", json={"text": STORY_RECOVERY})
    await client.post("/api/story/step")
    response = await client.post("/api/story/step")
    assert response.status_code == 409
    assert "read-back" in response.json()["message"]


# -- 8: confirmations and Flow phrasing ---------------------------------------------


@pytest.mark.parametrize(
    "text", ["Yes.", "Yes, go ahead.", "Yes please.", "Confirm.", "Okay, confirm."]
)
def test_spoken_confirmations(fixtures_dir: Path, text: str) -> None:
    assert Session("s-yes", fixtures_dir).grammar.is_confirmation(text)


@pytest.mark.parametrize("text", ["Yesterday's report", "Stop the run", "no"])
def test_not_confirmations(fixtures_dir: Path, text: str) -> None:
    assert not Session("s-no", fixtures_dir).grammar.is_confirmation(text)


def test_fillers_inside_an_approval(fixtures_dir: Path) -> None:
    grammar = Session("s-um", fixtures_dir).grammar
    text = "Approve reporting as long as it, um, only reads from approved summaries, please."
    assert grammar.parse_approval(text) is not None


# -- 9, 10: sessions and rate limits on a public Space --------------------------------


async def test_full_sandbox_refuses_new_visitors_instead_of_evicting(
    manager: SessionManager,
) -> None:
    first = _client(manager)
    await first.post("/api/session")
    for _ in range(2):
        await _client(manager).post("/api/session")
    response = await _client(manager).post("/api/session")
    assert response.status_code == 503
    assert (await first.get("/api/state")).status_code == 200


async def test_client_supplied_session_ids_are_not_trusted(manager: SessionManager) -> None:
    client = _client(manager)
    client.cookies.set("haegis_session", "x" * 3000)
    response = await client.post("/api/session")
    assert response.json()["session_id"] != "x" * 3000
    assert len(response.cookies["haegis_session"]) < 40


async def test_correct_is_rate_limited(manager: SessionManager) -> None:
    client = _client(manager)
    await _to_beat_8(client)
    plan = (await client.post("/api/recovery/interpret", json={"text": STORY_RECOVERY})).json()
    codes = [
        (
            await client.post(f"/api/recovery/{plan['id']}/correct", json={"text": STORY_RECOVERY})
        ).status_code
        for _ in range(4)
    ]
    assert codes[-1] == 429


# -- 11: confirm is tied to the read-back that was seen -------------------------------


async def test_confirm_with_a_stale_revision_is_refused(manager: SessionManager) -> None:
    client = _client(manager)
    await _to_beat_8(client)
    seen = (await client.post("/api/recovery/interpret", json={"text": STORY_RECOVERY})).json()
    await client.post(
        f"/api/recovery/{seen['id']}/correct",
        json={"text": "Stop this reporting run. Keep the support work."},
    )
    response = await client.post(
        f"/api/recovery/{seen['id']}/confirm", json={"revision": seen["revision"]}
    )
    assert response.status_code == 409
    assert "read it again" in response.json()["message"]


# -- 12: a send that completes a route is queued before it is held --------------------


async def test_queued_is_recorded_before_held_and_replay_agrees(fixtures_dir: Path) -> None:
    session = Session("s-order", fixtures_dir)
    decision = session.decisions.propose(
        DecisionProposal(
            statement="Reporting may proceed",
            subject="Reporting",
            actor="reporting-agent",
            conditions=[
                ConditionProposal(
                    predicate=NoUndeclaredPath(source="crm", sink="webhook"), plain="no route"
                )
            ],
        ),
        "",
    )
    session.decisions.confirm(decision.id)
    session.decisions.start_run("R-1", decision.id)
    support = session.decisions.start_run("S-1", "D-0")
    await session.agent(support.id).call("crm.read_customer_records", {"customer_id": "cust-1042"})
    await session.agent(support.id).call("scratchpad.write", {"item": "n", "content": "x"})
    await session.agent(support.id).call("scratchpad.grant_access", {"grantee": "reporting-agent"})
    await session.agent("R-1").call("scratchpad.read", {})
    session.world.write("d", "report_store/drafts", "r", "reporting-agent")
    await session.agent("R-1").call("webhook.send_report", {"item": "d"})
    kinds = [e.kind for e in session.ledger.events() if e.kind.startswith("action.")]
    assert kinds.index("action.queued") < kinds.index("action.held")
    replayed = DecisionGraph.replay(SessionLedger.parse_jsonl(session.ledger.to_jsonl()))
    assert replayed.actions["A-1"] == session.gateway.outbox.get("A-1").status == "held"
    assert json.loads(session.ledger.to_jsonl().splitlines()[-1])
