"""Compensation: registered inverses only, and never over a later human edit."""

from __future__ import annotations

from pathlib import Path

from aegis.ledger import LedgerEvent
from aegis.recovery.compensation import CompensationRegistry
from aegis.scenario import Session


def _write_by(session: Session, run_id: str, tool: str) -> LedgerEvent:
    return next(
        e
        for e in session.ledger.events()
        if e.kind == "gateway.call"
        and e.run_id == run_id
        and e.payload["tool"] == tool
        and e.payload["outcome"] == "executed"
    )


def test_registry_reads_the_catalogue(fixtures_dir: Path) -> None:
    session = Session("s-comp0", fixtures_dir)
    registry = CompensationRegistry(session.catalogue)
    assert registry.inverse_of("report_store.write_draft") == "report_store.restore_draft"
    assert registry.inverse_of("scratchpad.grant_access") == "scratchpad.revoke_access"
    assert registry.inverse_of("report_store.write_summary") is None
    assert registry.is_irreversible("webhook.send_report")


async def test_human_edit_survives(fixtures_dir: Path) -> None:
    session = Session("s-comp1", fixtures_dir)
    await session.run_to(4)
    write = _write_by(session, "R-1", "report_store.write_draft")
    result = await CompensationRegistry(session.catalogue).compensate(
        write, session.recovery_agent()
    )
    assert result.status == "conflict"
    draft = session.world.items["draft-1"]
    assert (draft.version, draft.writer) == (2, "teammate")
    assert str(draft.content).endswith("Reviewed by the support lead.")
    assert result.evidence == {
        "item": "draft-1",
        "produced_version": 1,
        "current_version": 2,
        "current_writer": "teammate",
    }


async def test_unchanged_draft_is_restored(fixtures_dir: Path) -> None:
    session = Session("s-comp2", fixtures_dir)
    await session.run_to(3)
    write = _write_by(session, "R-1", "report_store.write_draft")
    result = await CompensationRegistry(session.catalogue).compensate(
        write, session.recovery_agent()
    )
    assert result.status == "succeeded"
    draft = session.world.items["draft-1"]
    assert (draft.content, draft.writer) == (None, "sentra-recovery")


async def test_grant_is_revoked_through_its_inverse(fixtures_dir: Path) -> None:
    session = Session("s-comp3", fixtures_dir)
    await session.run_to(5)
    grant = _write_by(session, "S-1", "scratchpad.grant_access")
    result = await CompensationRegistry(session.catalogue).compensate(
        grant, session.recovery_agent()
    )
    assert result.status == "succeeded"
    assert ("reporting-agent", "scratchpad") not in session.world.grants


async def test_delivered_send_escalates(fixtures_dir: Path) -> None:
    session = Session("s-comp4", fixtures_dir)
    await session.run_to(3)
    await session.gateway.release_due()
    send = next(e for e in session.ledger.events() if e.kind == "action.delivered")
    result = await CompensationRegistry(session.catalogue).compensate_send(
        send.payload["action_id"], session.gateway.outbox
    )
    assert result.status == "escalated"
    assert "cannot be recalled" in result.detail


async def test_write_without_inverse_escalates(fixtures_dir: Path) -> None:
    session = Session("s-comp5", fixtures_dir)
    await session.run_to(2)
    summary = _write_by(session, "S-1", "report_store.write_summary")
    result = await CompensationRegistry(session.catalogue).compensate(
        summary, session.recovery_agent()
    )
    assert result.status == "escalated"
