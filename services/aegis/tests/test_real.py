"""The gateway in front of someone's own MCP server, through FastMCP's proxy."""

from __future__ import annotations

import mcp.types as mt
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from aegis.clock import LogicalClock
from aegis.ledger import SessionLedger
from aegis.real import build_real_gateway


def _their_server() -> FastMCP:
    server = FastMCP("their-notes")

    @server.tool
    def read_note(name: str) -> str:
        return f"note {name}"

    return server


async def test_calls_are_recorded_with_the_connection_identity() -> None:
    ledger = SessionLedger("s-real", LogicalClock())
    proxy, _ = build_real_gateway(
        _their_server(),
        ledger=ledger,
        tools={"read_note": {"effect": "read", "resource": "notes"}},
    )
    info = mt.Implementation(name="desktop-client", version="1")
    async with Client(proxy, client_info=info) as client:
        result = await client.call_tool("read_note", {"name": "a"})
    assert result.data == "note a"
    [call] = [e for e in ledger.events() if e.kind == "gateway.call"]
    assert call.actor == "desktop-client"
    assert call.payload["outcome"] == "executed"
    assert call.payload["resource"] == "notes"


async def test_a_deny_rule_refuses_through_the_proxy() -> None:
    ledger = SessionLedger("s-real", LogicalClock())
    proxy, _ = build_real_gateway(
        _their_server(), ledger=ledger, deny={("desktop-client", "read_note")}
    )
    info = mt.Implementation(name="desktop-client", version="1")
    async with Client(proxy, client_info=info) as client:
        with pytest.raises(ToolError, match="control_deny"):
            await client.call_tool("read_note", {"name": "a"})
    assert ledger.events()[-1].payload["outcome"] == "rejected"
