"""The HTTP API: per-visitor sandboxes, commands and the event stream."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from sentra.api.app import create_app
from sentra.api.sessions import SessionManager

STORY_APPROVAL = (
    "Approve reporting, on the condition that the Reporting Agent only reads from the "
    "approved, sanitized report store."
)


@pytest.fixture
def client(fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    monkeypatch.setenv("SENTRA_INTERPRETER", "off")
    app = create_app(SessionManager(fixtures_dir, cap=3, idle_minutes=30, interpret_per_minute=3))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://sentra.local")


def _events(body: str) -> list[dict]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in body.splitlines():
        if not line:
            if current:
                events.append(current)
            current = {}
            continue
        key, _, value = line.partition(": ")
        current[key] = value
    if current:
        events.append(current)
    return events


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.json() == {"status": "ok"}


async def test_session_snapshot_is_labelled(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/session")
    state = response.json()
    assert "sentra_session" in response.cookies
    assert state["labels"] == {"data": "Fictional data", "mode": "Live sandbox"}
    assert state["decisions"][0]["id"] == "D-0"
    assert state["beat"] == -1
    assert [b["n"] for b in state["storyline"]][:3] == [0, 1, 2]


async def test_sessions_are_isolated(client: httpx.AsyncClient) -> None:
    other = httpx.AsyncClient(transport=client._transport, base_url="http://sentra.local")  # noqa: SLF001
    await client.post("/api/session")
    await other.post("/api/session")
    for _ in range(4):
        await client.post("/api/story/step")
    mine = (await client.get("/api/state")).json()
    theirs = (await other.get("/api/state")).json()
    assert mine["beat"] == 3 and theirs["beat"] == -1
    assert mine["session_id"] != theirs["session_id"]
    ledger = (await other.get("/api/ledger.jsonl")).text
    assert all(
        json.loads(line)["session_id"] == theirs["session_id"] for line in ledger.splitlines()
    )


async def test_sse_resume_has_no_duplicates(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    await client.post("/api/story/step")
    await client.post("/api/story/step")
    first = _events((await client.get("/api/events", params={"follow": "false"})).text)
    ids = [int(e["id"]) for e in first]
    assert ids == sorted(set(ids))
    middle = ids[len(ids) // 2]
    resumed = _events(
        (
            await client.get(
                "/api/events", params={"follow": "false"}, headers={"Last-Event-ID": str(middle)}
            )
        ).text
    )
    assert [int(e["id"]) for e in resumed] == [i for i in ids if i > middle]
    assert {e["event"] for e in first} >= {"ledger", "decision"}


async def test_double_confirm_is_idempotent(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    proposed = (await client.post("/api/decisions/interpret", json={"text": STORY_APPROVAL})).json()
    decision_id = proposed["decision"]["id"]
    assert proposed["read_back"].startswith("I will record this approval: Reporting may proceed.")
    for _ in range(2):
        response = await client.post(f"/api/decisions/{decision_id}/confirm")
        assert response.status_code == 200
    ledger = (await client.get("/api/ledger.jsonl")).text
    confirms = [
        line
        for line in ledger.splitlines()
        if json.loads(line)["kind"] == "decision.confirmed"
        and json.loads(line)["decision_id"] == decision_id
    ]
    assert len(confirms) == 1


async def test_story_step_skips_an_approval_already_dictated(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    proposed = (await client.post("/api/decisions/interpret", json={"text": STORY_APPROVAL})).json()
    await client.post(f"/api/decisions/{proposed['decision']['id']}/confirm")
    for _ in range(2):
        await client.post("/api/story/step")
    state = (await client.get("/api/state")).json()
    assert [d["id"] for d in state["decisions"]] == ["D-0", "D-1"]


async def test_interpret_rate_limited(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    codes = [
        (await client.post("/api/decisions/interpret", json={"text": STORY_APPROVAL})).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]


async def test_error_envelope(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    response = await client.post("/api/decisions/D-9/confirm")
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "message": "No decision 'D-9'."}
    response = await client.post("/api/decisions/interpret", json={"text": "hello there"})
    assert response.status_code == 422
    assert response.json()["error"] == "not_understood"
    response = await client.post("/api/decisions/interpret", json={"text": "x" * 3000})
    assert response.json()["error"] == "text_too_long"


async def test_recovery_by_dictation_then_spoken_confirm(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    for _ in range(7):
        await client.post("/api/story/step")
    assert (await client.get("/api/state")).json()["beat"] == 8
    plan = (
        await client.post(
            "/api/recovery/interpret",
            json={
                "text": "Stop this reporting run, remove its scratchpad access, and rebuild the "
                "report from approved summaries. Keep the support work."
            },
        )
    ).json()
    assert plan["status"] == "read_back"
    confirmed = (await client.post("/api/recovery/interpret", json={"text": "Yes, run it."})).json()
    assert confirmed["id"] == plan["id"] and confirmed["status"] == "executing"
    state = (await client.get("/api/state")).json()
    assert state["conflicts"][0]["item"] == "draft-1"
    resolved = await client.post(
        f"/api/conflicts/{state['conflicts'][0]['id']}/resolve", json={"choice": "overwrite"}
    )
    assert resolved.status_code == 409
    while not (await client.get("/api/state")).json()["at_end"]:
        await client.post("/api/story/step")
    record = (await client.get("/api/record")).json()
    assert record["summary"][-1] == "Support work preserved."


async def test_human_edit_endpoint(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    for _ in range(4):
        await client.post("/api/story/step")
    response = await client.post("/api/items/draft-1/human-edit", json={"content": "Edited."})
    assert response.status_code == 200
    item = next(i for i in response.json()["items"] if i["id"] == "draft-1")
    assert (item["version"], item["writer"]) == (2, "teammate")


async def test_engine_routes_stay_available(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


STANDING_ORDER = (
    "From now on, an agent that can send outside never reads from a store nobody declared."
)


async def test_standing_order_over_http(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    for _ in range(12):  # through beat 14, the closed record
        assert (await client.post("/api/story/step")).status_code == 200
    response = await client.post("/api/standing-orders/interpret", json={"text": STANDING_ORDER})
    assert response.status_code == 200
    body = response.json()
    assert body["order"]["id"] == "SO-1"
    assert "Checked as: NoUndeclaredReads(senders)." in body["read_back"]
    confirmed = await client.post("/api/standing-orders/SO-1/confirm")
    assert confirmed.json()["order"]["status"] == "active"

    # The storyline's own beats leave the operator's confirmed order alone.
    state = (await client.post("/api/story/play")).json()
    assert state["at_end"]
    assert [o["id"] for o in state["standing_orders"]] == ["SO-1"]

    # A new session for the same visitor is next week: the order comes with it.
    state = (await client.post("/api/story/reset")).json()
    assert state["storyline_name"] == "next-week"
    assert state["standing_orders"][0]["status"] == "active"
    state = (await client.post("/api/story/play")).json()
    assert [a["order_id"] for a in state["alerts"]] == ["SO-1"]
    assert state["deliveries"][0]["item"] == "draft-1"


async def test_standing_order_bad_verb_and_state(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    await client.post("/api/standing-orders/interpret", json={"text": STANDING_ORDER})
    bad = await client.post("/api/standing-orders/SO-1/frobnicate")
    assert (bad.status_code, bad.json()["error"]) == (404, "not_found")
    early = await client.post("/api/standing-orders/SO-1/revoke")
    assert (early.status_code, early.json()["error"]) == (409, "not_allowed")
    missing = await client.post("/api/standing-orders/SO-9/confirm")
    assert (missing.status_code, missing.json()["error"]) == (404, "not_found")
    unclear = await client.post("/api/standing-orders/interpret", json={"text": "be careful"})
    assert (unclear.status_code, unclear.json()["error"]) == (422, "not_understood")


async def test_new_visitor_starts_with_no_orders(client: httpx.AsyncClient) -> None:
    await client.post("/api/session")
    await client.post("/api/standing-orders/interpret", json={"text": STANDING_ORDER})
    await client.post("/api/standing-orders/SO-1/confirm")
    other = httpx.AsyncClient(transport=client._transport, base_url="http://sentra.local")  # noqa: SLF001
    state = (await other.post("/api/session")).json()
    assert state["standing_orders"] == []
    assert state["storyline_name"] == "storyline"
