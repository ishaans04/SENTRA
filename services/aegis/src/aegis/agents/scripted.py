"""Scripted agents: MCP clients that make exactly the calls the storyline says.

The judge path makes zero model calls, so the demo agents are scripted. They
are still real MCP clients talking to the real gateway over in-memory transport,
which is the point: what the gateway enforces on them it would enforce on a
model-driven agent too.

A rejected call does not crash the agent. It comes back as a failed result, the
way a real agent would see a tool error and carry on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastmcp.exceptions import ToolError

from aegis.gateway.server import Gateway


@dataclass(frozen=True)
class CallResult:
    ok: bool
    data: Any = None
    error: str | None = None


class ScriptedAgent:
    def __init__(self, gateway: Gateway, run_id: str) -> None:
        self.gateway = gateway
        self.run_id = run_id

    async def call(self, tool: str, args: dict[str, Any]) -> CallResult:
        wire_name = self.gateway.catalogue.get(tool).wire_name
        try:
            async with self.gateway.client_for(self.run_id) as client:
                result = await client.call_tool(wire_name, args)
        except ToolError as exc:
            return CallResult(ok=False, error=str(exc))
        return CallResult(ok=True, data=result.data)
