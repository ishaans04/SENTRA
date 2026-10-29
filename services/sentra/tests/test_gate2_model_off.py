"""Gate 2: model-off replay holds and rejects."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentra.decisions.graph import DecisionGraph
from sentra.ledger import SessionLedger
from sentra.scenario import Session


async def test_model_off_replay_holds_and_rejects(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SENTRA_INTERPRETER", "off")
    session = Session("s-gate2", fixtures_dir)
    await session.run_to(8)

    d1 = session.decisions.get("D-1")
    assert (d1.status, d1.epoch) == ("suspended", 2)
    assert session.gateway.outbox.get("A-1").status == "held"
    retry = [
        e
        for e in session.ledger.events()
        if e.kind == "gateway.call"
        and e.run_id == "R-1"
        and e.payload["tool"] == "webhook.send_report"
    ][-1]
    assert (retry.payload["outcome"], retry.payload["reason"]) == ("rejected", "stale_epoch")
    assert session.world.count("webhook.send_report") == 0
    assert not [e for e in session.ledger.events() if e.kind.startswith("interpretation.")]

    replayed = DecisionGraph.replay(SessionLedger.parse_jsonl(session.ledger.to_jsonl()))
    assert replayed.snapshot() == session.decisions.graph.snapshot()
    assert replayed.runs["R-1"] == "stale"
    assert replayed.actions["A-1"] == "held"


async def test_two_runs_write_byte_identical_ledgers(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SENTRA_INTERPRETER", "off")
    first, second = Session("s-same", fixtures_dir), Session("s-same", fixtures_dir)
    await first.run_to(8)
    await second.run_to(8)
    assert first.ledger.to_jsonl() == second.ledger.to_jsonl()


async def test_storyline_approval_goes_through_the_grammar(fixtures_dir: Path) -> None:
    session = Session("s-gate2b", fixtures_dir)
    await session.run_to(1)
    proposed = [e for e in session.ledger.events() if e.kind == "decision.proposed"][-1]
    assert proposed.payload["decision"]["dictated_text"].startswith("Approve reporting")
    assert proposed.producer == "interpret"
