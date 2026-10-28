"""The four fictional tool servers, called directly over in-memory MCP."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from aegis.tools.catalogue import Catalogue
from aegis.tools.servers import build_tool_servers
from aegis.world import CALLER, World


@pytest.fixture
def world() -> World:
    return World.seed()


async def _call(world: World, server: str, tool: str, args: dict, caller: str) -> object:
    CALLER.set(caller)
    async with Client(build_tool_servers(world)[server]) as client:
        return (await client.call_tool(tool, args)).data


async def test_write_draft_bumps_version(world: World) -> None:
    first = await _call(
        world, "report_store", "write_draft", {"item": "draft-1", "content": "a"}, "reporting-agent"
    )
    second = await _call(
        world, "report_store", "write_draft", {"item": "draft-1", "content": "b"}, "reporting-agent"
    )
    assert first == {"item": "draft-1", "version": 1}
    assert second == {"item": "draft-1", "version": 2}
    assert world.items["draft-1"].writer == "reporting-agent"


async def test_scratchpad_read_requires_grant(world: World) -> None:
    await _call(world, "scratchpad", "write", {"item": "note-1", "content": "x"}, "support-agent")
    with pytest.raises(ToolError, match="no access"):
        await _call(world, "scratchpad", "read", {}, "reporting-agent")
    await _call(
        world, "scratchpad", "grant_access", {"grantee": "reporting-agent"}, "support-agent"
    )
    notes = await _call(world, "scratchpad", "read", {}, "reporting-agent")
    assert notes == [{"item": "note-1", "content": "x"}]


async def test_send_report_only_counts(world: World) -> None:
    await _call(
        world, "report_store", "write_draft", {"item": "draft-1", "content": "r"}, "reporting-agent"
    )
    receipt = await _call(world, "webhook", "send_report", {"item": "draft-1"}, "gateway-outbox")
    assert receipt == {"delivered": "draft-1", "version": 1}
    assert world.deliveries == [{"item": "draft-1", "version": 1, "content": "r"}]
    assert world.count("webhook.send_report") == 1


async def test_restore_draft_to_version_zero_withdraws_it(world: World) -> None:
    await _call(
        world, "report_store", "write_draft", {"item": "draft-1", "content": "r"}, "reporting-agent"
    )
    await _call(
        world, "report_store", "restore_draft", {"item": "draft-1", "to_version": 0}, "recovery"
    )
    assert world.items["draft-1"].content is None
    assert world.items["draft-1"].version == 2


def test_catalogue_maps_wire_names(fixtures_dir: Path) -> None:
    catalogue = Catalogue.load(fixtures_dir / "tools.yaml")
    spec = catalogue.by_wire("report_store_write_draft")
    assert spec.name == "report_store.write_draft"
    assert spec.inverse == "report_store.restore_draft"
    assert catalogue.get("webhook.send_report").effect == "send"
