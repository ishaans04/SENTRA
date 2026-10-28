"""The whole storyline, beats 0 to 14, headless and with the model off (AC-06 to AC-11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.scenario import Session


def _kinds(session: Session, kind: str) -> list:
    return [e for e in session.ledger.events() if e.kind == kind]


async def test_full_storyline_headless(fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_INTERPRETER", "off")
    session = Session("s-story", fixtures_dir)
    await session.run_to(14)
    assert session.at_end

    plan = session.recovery.get("P-1")
    assert plan.interpreted_by == "grammar"
    assert plan.status == "verified_with_conflicts"

    # AC-06: R-1 and its held send are cancelled; the containment control is applied.
    assert session.decisions.graph.runs["R-1"] == "cancelled"
    assert session.decisions.graph.actions["A-1"] == "cancelled"
    assert session.bridge.projection.applied_controls == ["deny-reporting-scratchpad-read"]

    # AC-07: the draft correction stops as a conflict and keeps the human version.
    [conflict] = _kinds(session, "recovery.step_conflict")
    assert conflict.payload["evidence"]["item"] == "draft-1"
    assert session.world.items["draft-1"].writer == "teammate"

    # AC-08: D-1 renewed, R-2 ran with fresh context from approved sources, its send released.
    d1 = session.decisions.get("D-1")
    assert (d1.status, d1.epoch) == ("active", 2)
    assert session.decisions.graph.runs["R-2"] == "completed"
    assert session.gateway.state.runs["R-2"].fresh_context
    assert session.decisions.graph.actions["A-2"] == "delivered"
    assert [d["item"] for d in session.world.deliveries] == ["draft-2"]

    # AC-09: four checks, all passing, recorded as checked evidence.
    checks = _kinds(session, "verification.check")
    assert [(c.payload["name"], c.payload["passed"]) for c in checks] == [
        ("route_closed", True),
        ("stale_run_rejected", True),
        ("replacement_completed", True),
        ("preserved_work_unchanged", True),
    ]

    # AC-10: the record closes with approval, evidence, controls, outcome and the conflict.
    [closed] = _kinds(session, "record.closed")
    record = closed.payload
    assert record["approval"]["id"] == "D-1"
    assert record["finding"]["rule_id"] == "PS-001"
    assert record["plan"]["controls"] == ["deny-reporting-scratchpad-read"]
    assert record["summary"] == [
        "Affected send cancelled.",
        "Unexpected access removed.",
        "Report rebuilt from approved sources.",
        "Support work preserved.",
    ]
    assert len(record["conflicts"]) == 1

    # AC-11 and INV-2: none of this needed a model.
    assert not _kinds(session, "interpretation.requested")


async def test_storyline_readback_matches_the_prd(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AEGIS_INTERPRETER", "off")
    session = Session("s-story2", fixtures_dir)
    await session.run_to(9)
    plan = session.recovery.get("P-1")
    assert plan.status == "read_back"
    assert plan.read_back.startswith(
        "I will:\n 1. Cancel reporting run R-1 and its held external send A-1."
    )
    assert "I will keep: all Support Agent work." in plan.read_back
