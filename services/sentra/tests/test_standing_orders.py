"""Standing orders: what the operator says should always hold, kept across sessions."""

from __future__ import annotations

from pathlib import Path

from sentra.engine_bridge import EngineBridge
from sentra.gateway.enforce import Verdict, enforce
from sentra.gateway.state import GatewayState, RunState, StandingRule, ToolCall
from sentra.scenario import Session
from sentra.standing.book import StandingOrderBook
from sentra.standing.models import (
    NoUndeclaredReads,
    OrderProvenance,
    StandingOrder,
    compile_order,
)
from sentra.tools.catalogue import Catalogue

DEMO = "From now on, an agent that can send outside never reads from a store nobody declared."

SENDERS_RULE = StandingRule(
    order_id="SO-1",
    actors=frozenset({"reporting-agent"}),
    resources=frozenset({"scratchpad"}),
)


def _order(
    order_id: str = "SO-1", status: str = "proposed", actor: str | None = None
) -> StandingOrder:
    return StandingOrder(
        id=order_id,
        rule=NoUndeclaredReads(actor=actor),
        plain="an agent that can send outside never reads from storage nobody declared",
        dictated_text=DEMO,
        status=status,  # type: ignore[arg-type]
        provenance=OrderProvenance(session_id="s-test", decided_at="2026-10-30T09:00:00Z"),
    )


# -- the book ------------------------------------------------------------------


def test_book_round_trips_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "orders.jsonl"
    book = StandingOrderBook(path)
    book.put(_order("SO-1", "proposed"))
    book.put(_order("SO-1", "active"))
    book.put(_order("SO-2", "discarded"))

    reopened = StandingOrderBook(path)
    assert [o.id for o in reopened.active()] == ["SO-1"]
    assert reopened.next_id() == "SO-3"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


def test_in_memory_book_writes_nothing(tmp_path: Path) -> None:
    book = StandingOrderBook()
    book.put(_order())
    assert list(tmp_path.iterdir()) == []
    assert book.get("SO-1").status == "proposed"


# -- compiling against the estate ------------------------------------------------


def test_compile_senders_reach_every_undeclared_store(fixtures_dir: Path) -> None:
    manifest = EngineBridge(fixtures_dir / "manifest.yaml").manifest
    rule = compile_order(_order(status="active"), manifest)
    assert rule.order_id == "SO-1"
    assert rule.actors == {"reporting-agent"}
    assert rule.resources == {"scratchpad"}


def test_compile_named_actor(fixtures_dir: Path) -> None:
    manifest = EngineBridge(fixtures_dir / "manifest.yaml").manifest
    rule = compile_order(_order(status="active", actor="support-agent"), manifest)
    assert rule.actors == {"support-agent"}
    assert NoUndeclaredReads(actor="support-agent").typed() == "NoUndeclaredReads(support-agent)"
    assert NoUndeclaredReads().typed() == "NoUndeclaredReads(senders)"


# -- the gateway -----------------------------------------------------------------


def _verdict(fixtures_dir: Path, actor: str, tool: str) -> Verdict:
    catalogue = Catalogue.load(fixtures_dir / "tools.yaml")
    session = Session("s-verdict", fixtures_dir)
    state = GatewayState(
        runs={"R-9": RunState(id="R-9", actor=actor, decision_id="D-0", epoch=1)},
        decisions=session.decisions.graph.decisions,
        standing_rules=[SENDERS_RULE],
    )
    return enforce(ToolCall("R-9", actor, catalogue.get(tool), {}), state)


def test_standing_order_refuses_a_sender_reading_undeclared_storage(fixtures_dir: Path) -> None:
    verdict = _verdict(fixtures_dir, "reporting-agent", "scratchpad.read")
    assert verdict == Verdict("reject", "standing_order", ref="SO-1")


def test_standing_order_leaves_other_work_alone(fixtures_dir: Path) -> None:
    assert _verdict(fixtures_dir, "support-agent", "scratchpad.write").outcome == "forward"
    assert _verdict(fixtures_dir, "support-agent", "scratchpad.read").outcome == "forward"
    assert (
        _verdict(fixtures_dir, "reporting-agent", "report_store.read_summaries").outcome
        == "forward"
    )


async def test_refused_call_is_recorded_with_its_order(fixtures_dir: Path) -> None:
    session = Session("s-refused", fixtures_dir)
    await session.run_to(3)
    session.gateway.state.standing_rules.append(SENDERS_RULE)
    result = await session.agent("R-1").call("scratchpad.read", {})
    assert (result.ok, result.error) == (False, "standing_order")
    last = [e for e in session.ledger.events() if e.kind == "gateway.call"][-1]
    assert last.payload["outcome"] == "rejected"
    assert last.payload["reason"] == "standing_order"
    assert last.payload["order_id"] == "SO-1"
    assert session.bridge.open_findings() == []
