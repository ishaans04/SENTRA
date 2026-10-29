"""The gateway: the only route from an agent to a tool."""

from __future__ import annotations

from pathlib import Path

import mcp.types as mt
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from sentra.clock import LogicalClock
from sentra.decisions.models import Decision
from sentra.gateway.server import Gateway
from sentra.gateway.state import RunState
from sentra.ledger import LedgerEvent, SessionLedger
from sentra.tools.catalogue import Catalogue
from sentra.world import World


@pytest.fixture
def gateway(fixtures_dir: Path) -> Gateway:
    ledger = SessionLedger("s-test", LogicalClock())
    gw = Gateway(World.seed(), ledger, Catalogue.load(fixtures_dir / "tools.yaml"))
    for decision_id, actor in (("D-0", "support-agent"), ("D-1", "reporting-agent")):
        gw.state.decisions[decision_id] = Decision(
            id=decision_id, statement="", subject="", actor=actor, status="active"
        )
    gw.register_run(RunState(id="R-1", actor="reporting-agent", decision_id="D-1", epoch=1))
    gw.register_run(RunState(id="S-1", actor="support-agent", decision_id="D-0", epoch=1))
    return gw


def _calls(gateway: Gateway) -> list[LedgerEvent]:
    return [e for e in gateway.ledger.events() if e.kind == "gateway.call"]


async def test_spoofed_actor_argument_is_ignored(gateway: Gateway) -> None:
    async with gateway.client_for("R-1") as client:
        await client.call_tool(
            "report_store_write_draft",
            {"item": "draft-1", "content": "x"},
        )
    assert gateway.world.items["draft-1"].writer == "reporting-agent"
    assert _calls(gateway)[0].actor == "reporting-agent"


async def test_hand_built_client_is_refused(gateway: Gateway) -> None:
    forged = Client(gateway.mcp, client_info=mt.Implementation(name="R-1", version="1"))
    async with forged as client:
        with pytest.raises(ToolError, match="unknown_connection"):
            await client.call_tool("report_store_read_summaries", {})
    assert gateway.world.count("report_store.read_summaries") == 0
    assert _calls(gateway)[0].payload["outcome"] == "rejected"


async def test_every_call_is_recorded(gateway: Gateway) -> None:
    async with gateway.client_for("S-1") as client:
        await client.call_tool("crm_read_customer_records", {"customer_id": "cust-1042"})
        with pytest.raises(ToolError):
            await client.call_tool("crm_read_customer_records", {"customer_id": "nobody"})
    outcomes = [e.payload["outcome"] for e in _calls(gateway)]
    assert outcomes == ["executed", "failed"]
    assert _calls(gateway)[0].payload["tool"] == "crm.read_customer_records"
    assert _calls(gateway)[0].payload["resource"] == "crm"


async def test_send_is_queued_not_delivered(gateway: Gateway) -> None:
    async with gateway.client_for("R-1") as client:
        await client.call_tool("report_store_write_draft", {"item": "draft-1", "content": "r"})
        receipt = await client.call_tool("webhook_send_report", {"item": "draft-1"})
    assert receipt.data == {"queued": "A-1"}
    assert gateway.world.count("webhook.send_report") == 0
    assert gateway.outbox.get("A-1").status == "queued"
    kinds = [e.kind for e in gateway.ledger.events()]
    assert kinds[-2:] == ["gateway.call", "action.queued"]


async def test_cancelled_run_is_rejected(gateway: Gateway) -> None:
    gateway.state.runs["R-1"].status = "cancelled"
    async with gateway.client_for("R-1") as client:
        with pytest.raises(ToolError, match="run_cancelled"):
            await client.call_tool("report_store_read_summaries", {})
    assert gateway.world.count("report_store.read_summaries") == 0


async def test_observer_sees_recorded_calls(gateway: Gateway) -> None:
    seen: list[str] = []
    gateway.observers.append(lambda event: seen.append(event.payload["outcome"]))
    async with gateway.client_for("S-1") as client:
        await client.call_tool("crm_read_customer_records", {"customer_id": "cust-1042"})
    assert seen == ["executed"]
