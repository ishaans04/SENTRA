"""Standing orders: what the operator says should always hold, kept across sessions."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentra.decisions.graph import DecisionGraph
from sentra.decisions.service import DecisionError
from sentra.engine_bridge import EngineBridge
from sentra.gateway.enforce import Verdict, enforce
from sentra.gateway.state import GatewayState, RunState, StandingRule, ToolCall
from sentra.interpret.providers import ProviderError
from sentra.ledger import SessionLedger
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


def test_book_keeps_the_latest_version_of_each_order() -> None:
    book = StandingOrderBook()
    order = _order("SO-1", "proposed")
    book.put(order)
    order.status = "active"
    assert book.get("SO-1").status == "proposed"
    book.put(order)
    book.put(_order("SO-2", "discarded"))
    assert [o.id for o in book.active()] == ["SO-1"]
    assert [o.id for o in book.orders()] == ["SO-1", "SO-2"]
    assert book.next_id() == "SO-3"
    with pytest.raises(KeyError, match="No standing order 'SO-9'"):
        book.get("SO-9")


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
    session.orders.put(_order(status="active"))
    session.gateway.state.standing_rules.append(SENDERS_RULE)
    result = await session.agent("R-1").call("scratchpad.read", {})
    assert (result.ok, result.error) == (False, "standing_order")
    last = [e for e in session.ledger.events() if e.kind == "gateway.call"][-1]
    assert last.payload["outcome"] == "rejected"
    assert last.payload["reason"] == "standing_order"
    assert last.payload["order_id"] == "SO-1"
    assert session.bridge.open_findings() == []


# -- dictation -------------------------------------------------------------------


def test_grammar_reads_the_demo_sentence(fixtures_dir: Path) -> None:
    proposal = Session("s-g1", fixtures_dir).grammar.parse_standing_order(DEMO)
    assert proposal is not None
    assert proposal.rule.actor is None
    assert proposal.plain == (
        "an agent that can send outside never reads from storage nobody declared"
    )


def test_grammar_reads_a_named_agent(fixtures_dir: Path) -> None:
    grammar = Session("s-g2", fixtures_dir).grammar
    proposal = grammar.parse_standing_order(
        "Going forward, the reporting agent must never read from undeclared storage."
    )
    assert proposal is not None
    assert proposal.rule.actor == "reporting-agent"
    assert proposal.plain == "the Reporting Agent never reads from storage nobody declared"


async def test_grammar_refuses_unknown_phrasing(fixtures_dir: Path) -> None:
    session = Session("s-g3", fixtures_dir)
    assert session.grammar.parse_standing_order("remember to be careful") is None
    assert session.grammar.parse_standing_order("From now on, Bob never reads from x.") is None
    with pytest.raises(ValueError, match="^I could not read that as a standing order"):
        await session.interpreter.standing_order("remember to be careful")


def test_model_output_naming_an_unknown_agent_is_refused(fixtures_dir: Path) -> None:
    session = Session("s-g4", fixtures_dir)
    raw = {"rule": {"kind": "NoUndeclaredReads", "actor": "ghost-agent"}, "plain": "x"}
    with pytest.raises(ProviderError, match="ghost-agent"):
        session.interpreter._check("standing_order", raw, "gemini")
    ok = {"rule": {"kind": "NoUndeclaredReads"}, "plain": "x"}
    assert session.interpreter._check("standing_order", ok, "gemini").rule.actor is None


# -- the session remembers --------------------------------------------------------


async def _remembered(fixtures_dir: Path) -> Session:
    """The whole storyline, ending with SO-1 confirmed."""
    session = Session("s-remember", fixtures_dir)
    await session.run_to(16)
    return session


def _next_week(fixtures_dir: Path, book: StandingOrderBook) -> Session:
    return Session("s-next", fixtures_dir, orders=book, storyline="next-week.yaml")


async def test_read_back_names_the_incident(fixtures_dir: Path) -> None:
    session = Session("s-readback", fixtures_dir)
    await session.run_to(15)
    [proposed] = [e for e in session.ledger.events() if e.kind == "standing_order.proposed"]
    read_back = proposed.payload["read_back"]
    assert read_back.startswith(
        "I will keep this standing order: "
        "an agent that can send outside never reads from storage nobody declared."
    )
    assert "Checked as: NoUndeclaredReads(senders)." in read_back
    assert "Today it covers: Reporting Agent reading Shared scratchpad." in read_back
    assert "Why: PS-001 in session s-readback, citing 4 calls." in read_back
    assert read_back.endswith("Interpreted by: grammar (no model call)")
    assert session.order_read_back("SO-1") == read_back
    assert session.gateway.state.standing_rules == []


async def test_next_week_refuses_the_read_and_pauses_nothing(fixtures_dir: Path) -> None:
    first = await _remembered(fixtures_dir)
    session = _next_week(fixtures_dir, first.orders)
    assert [e.kind for e in session.ledger.events()][1] == "standing_order.loaded"
    await session.run_to(5)
    assert session.at_end

    kinds = [e.kind for e in session.ledger.events()]
    assert "finding.raised" not in kinds
    d1 = session.decisions.get("D-1")
    assert (d1.status, d1.epoch) == ("active", 1)
    assert [d["item"] for d in session.world.deliveries] == ["draft-1"]

    calls = [e for e in session.ledger.events() if e.kind == "gateway.call"]
    [refused] = [c for c in calls if c.payload["outcome"] == "rejected"]
    assert (refused.run_id, refused.payload["tool"]) == ("R-1", "scratchpad.read")
    assert (refused.payload["reason"], refused.payload["order_id"]) == ("standing_order", "SO-1")
    [write] = [c for c in calls if c.payload["tool"] == "scratchpad.write"]
    assert write.payload["outcome"] == "executed"

    [alert] = [e for e in session.ledger.events() if e.kind == "alert.raised"]
    assert alert.cites == [refused.event_id]
    assert alert.payload["order_id"] == "SO-1"
    assert alert.payload["text"] == (
        "Reporting Agent tried to read Shared scratchpad. Standing order SO-1 forbids it: "
        f"“{DEMO}” The read was refused and nothing else was stopped."
    )


async def test_unconfirmed_order_is_not_kept(fixtures_dir: Path) -> None:
    session = Session("s-unconfirmed", fixtures_dir)
    await session.run_to(15)
    assert session.orders.get("SO-1").status == "proposed"
    assert session.orders.active() == []
    assert session.gateway.state.standing_rules == []
    later = _next_week(fixtures_dir, session.orders)
    assert "standing_order.loaded" not in [e.kind for e in later.ledger.events()]
    session.discard_standing_order("SO-1")
    assert session.orders.get("SO-1").status == "discarded"


async def test_revoked_order_lifts_now_and_later(fixtures_dir: Path) -> None:
    session = await _remembered(fixtures_dir)
    assert [r.order_id for r in session.gateway.state.standing_rules] == ["SO-1"]
    session.revoke_standing_order("SO-1")
    assert session.gateway.state.standing_rules == []
    assert [e.kind for e in session.ledger.events()][-1] == "standing_order.revoked"
    with pytest.raises(DecisionError):
        session.confirm_standing_order("SO-1")

    later = _next_week(fixtures_dir, session.orders)
    await later.run_to(4)
    read = [
        e
        for e in later.ledger.events()
        if e.kind == "gateway.call" and e.payload["tool"] == "scratchpad.read"
    ]
    assert read[0].payload["outcome"] == "executed"
    assert [f.rule_id for f in later.bridge.open_findings()] == ["PS-001"]


async def test_next_week_ledger_replays_identically(fixtures_dir: Path) -> None:
    first = await _remembered(fixtures_dir)
    session = _next_week(fixtures_dir, first.orders)
    await session.run_to(5)
    replayed = DecisionGraph.replay(SessionLedger.parse_jsonl(session.ledger.to_jsonl()))
    assert replayed.snapshot() == session.decisions.graph.snapshot()


async def test_storyline_cannot_confirm_the_operators_order(fixtures_dir: Path) -> None:
    session = Session("s-operator", fixtures_dir)
    await session.run_to(14)
    await session.propose_standing_order(DEMO)
    with pytest.raises(ValueError, match="Confirm or discard the standing order read-back first."):
        await session.run_to(16)
