"""The gateway in front of your own MCP servers: the "one real result" (PRD §8.17).

``create_proxy`` puts a FastMCP proxy in front of real servers listed in a
standard MCP config. The same rule holds as in the sandbox: every call is
recorded in a ledger with the caller taken from the MCP connection (the client's
own name), never from arguments. If you describe your estate in a HIVE manifest
and map your tools to effects and resources, each call is also fed to the HIVE
engine and any finding is printed and recorded.

Only calls through this proxy are seen. It observes and records; it does not
hold, reject or undo anything on real systems unless you pass ``--deny`` rules,
and those only refuse calls through the proxy. Run it locally:

    uv run python -m aegis.real --config mcp.json \\
        [--manifest my-estate.yaml --tools my-tools.yaml] [--deny actor:tool ...]

then point your MCP client at it (stdio) instead of at the servers directly.
The ledger is written to ``.local/real-result.jsonl``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mcp.types as mt
import yaml
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server import create_proxy
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult

from aegis.clock import LogicalClock
from aegis.hive_bridge import HiveBridge
from aegis.ledger import LedgerEvent, SessionLedger


class ObservingMiddleware(Middleware):
    """Record every call; feed HIVE when the tool is mapped; refuse denied ones."""

    def __init__(
        self,
        ledger: SessionLedger,
        tools: dict[str, dict[str, str]],
        bridge: HiveBridge | None = None,
        deny: set[tuple[str, str]] | None = None,
    ) -> None:
        self.ledger = ledger
        self.tools = tools
        self.bridge = bridge
        self.deny = deny or set()
        self.findings: list[str] = []

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        name = context.message.name
        actor = "unknown-client"
        fctx = context.fastmcp_context
        if fctx is not None and fctx.session.client_params is not None:
            actor = fctx.session.client_params.clientInfo.name
        spec = self.tools.get(name, {})
        payload: dict[str, Any] = {
            "tool": name,
            "effect": spec.get("effect", "unmapped"),
            "resource": spec.get("resource", name),
            "args": dict(context.message.arguments or {}),
        }
        if (actor, name) in self.deny:
            self._record(actor, payload | {"outcome": "rejected", "reason": "control_deny"})
            raise ToolError("control_deny")
        try:
            result = await call_next(context)
        except ToolError as exc:
            self._record(actor, payload | {"outcome": "failed", "reason": str(exc)})
            raise
        self._record(actor, payload | {"outcome": "executed"})
        return result

    def _record(self, actor: str, payload: dict[str, Any]) -> LedgerEvent:
        event = self.ledger.append("gateway.call", "gateway", actor=actor, payload=payload)
        if self.bridge is not None and payload["effect"] != "unmapped":
            for finding in self.bridge.observe(event):
                self.ledger.append(
                    "finding.raised",
                    "hive",
                    cites=list(finding.evidence_event_ids),
                    payload=finding.model_dump(),
                )
                self.findings.append(f"{finding.rule_id}: {finding.title}")
        return event


def build_real_gateway(
    target: Any,
    *,
    ledger: SessionLedger,
    tools: dict[str, dict[str, str]] | None = None,
    manifest: str | Path | None = None,
    deny: set[tuple[str, str]] | None = None,
) -> tuple[FastMCP, ObservingMiddleware]:
    proxy = create_proxy(target, name="sentra-gateway")
    bridge = HiveBridge(manifest) if manifest else None
    middleware = ObservingMiddleware(ledger, tools or {}, bridge, deny)
    proxy.add_middleware(middleware)
    return proxy, middleware


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="MCP config JSON with mcpServers")
    parser.add_argument("--manifest", help="HIVE manifest describing your estate")
    parser.add_argument("--tools", help="YAML mapping tool name -> {effect, resource}")
    parser.add_argument("--deny", nargs="*", default=[], help="actor:tool pairs to refuse")
    parser.add_argument("--out", default=".local/real-result.jsonl")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    tools: dict[str, dict[str, str]] = {}
    if args.tools:
        tools = yaml.safe_load(Path(args.tools).read_text(encoding="utf-8")) or {}
    deny = {(actor, tool) for actor, _, tool in (rule.partition(":") for rule in args.deny)}
    ledger = SessionLedger("s-real", LogicalClock())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    def keep(event: LedgerEvent) -> None:
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(), sort_keys=True) + "\n")

    ledger.listeners.append(keep)
    proxy, _ = build_real_gateway(
        config,
        ledger=ledger,
        tools=tools,
        manifest=args.manifest,
        deny=deny,
    )
    proxy.run()


if __name__ == "__main__":
    main()
