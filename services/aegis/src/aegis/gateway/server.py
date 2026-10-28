"""The MCP gateway: one FastMCP server in front of the four tool servers.

Agents never see a tool server. They get a client from ``Gateway.client_for``,
which binds that connection to one run with a secret token in the MCP client
info. The enforcement middleware reads the run from the connection, never from
tool arguments (INV-3), asks ``enforce`` what to do, records the call in the
session ledger whatever the outcome (INV-4), and only then forwards, queues or
rejects it with a ``ToolError``.

Observers (the session) are told about every recorded call. That is how HIVE
sees live traffic and how a finding can reach the decision ledger.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any

import mcp.types as mt
from fastmcp import Client, FastMCP
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult

from aegis.gateway.enforce import Verdict, enforce
from aegis.gateway.outbox import Outbox, QueuedAction
from aegis.gateway.state import GatewayState, RunState, ToolCall
from aegis.ledger import LedgerEvent, SessionLedger
from aegis.tools.catalogue import Catalogue, ToolSpec
from aegis.tools.servers import build_tool_servers
from aegis.world import CALLER, World

CallObserver = Callable[[LedgerEvent], None]


class Gateway:
    def __init__(self, world: World, ledger: SessionLedger, catalogue: Catalogue) -> None:
        self.world = world
        self.ledger = ledger
        self.catalogue = catalogue
        self.state = GatewayState()
        self.outbox = Outbox()
        self.observers: list[CallObserver] = []
        self.servers = build_tool_servers(world)
        self.mcp: FastMCP = FastMCP("haegis-gateway")
        for name, server in self.servers.items():
            self.mcp.mount(server, namespace=name)
        self.mcp.add_middleware(EnforcementMiddleware(self))
        self._tokens: dict[str, str] = {}

    # -- runs and connections -------------------------------------------------

    def register_run(self, run: RunState) -> RunState:
        self.state.runs[run.id] = run
        return run

    def client_for(self, run_id: str) -> Client[FastMCPTransport]:
        """The only way an agent gets a connection. Bound to *run_id*."""
        if run_id not in self.state.runs:
            raise KeyError(f"No run {run_id!r}.")
        token = secrets.token_hex(8)
        self._tokens[token] = run_id
        info = mt.Implementation(name=f"{run_id}:{token}", version="1")
        return Client(self.mcp, client_info=info)

    def run_for_connection(self, client_name: str) -> RunState | None:
        _, _, token = client_name.partition(":")
        run_id = self._tokens.get(token)
        return self.state.runs.get(run_id) if run_id else None

    # -- the outbox -----------------------------------------------------------

    def queue_send(self, call: ToolCall, run: RunState) -> QueuedAction:
        """Accept a send into the outbox. Held at once if its decision is under review."""
        action = self.outbox.queue(run.id, run.decision_id, run.actor, call.tool.name, call.args)
        event = self.record_call(call, "queued", action_id=action.id)
        action.cites = [event.event_id]
        self.ledger.append(
            "action.queued",
            "gateway",
            actor=run.actor,
            run_id=run.id,
            decision_id=run.decision_id,
            epoch=run.epoch,
            cites=[event.event_id],
            payload={"action_id": action.id, "tool": call.tool.name, "args": call.args},
        )
        decision = self.state.decisions.get(run.decision_id)
        if decision is not None and decision.status == "needs_review" and decision.hold_rule:
            self.hold(action, cites=[event.event_id])
        return action

    def hold(self, action: QueuedAction, cites: list[str]) -> None:
        action.status = "held"
        self.ledger.append(
            "action.held",
            "gateway",
            actor=action.actor,
            run_id=action.run_id,
            decision_id=action.decision_id,
            cites=cites,
            payload={"action_id": action.id},
        )

    # -- recording ------------------------------------------------------------

    def record_call(
        self,
        call: ToolCall,
        outcome: str,
        *,
        reason: str | None = None,
        result: Any = None,
        action_id: str | None = None,
    ) -> LedgerEvent:
        run = self.state.runs.get(call.run_id or "")
        payload: dict[str, Any] = {
            "tool": call.tool.name,
            "effect": call.tool.effect,
            "resource": call.tool.resource,
            "args": call.args,
            "outcome": outcome,
        }
        if reason:
            payload["reason"] = reason
        if result is not None:
            payload["result"] = result
        if action_id:
            payload["action_id"] = action_id
        event = self.ledger.append(
            "gateway.call",
            "gateway",
            actor=call.actor,
            run_id=call.run_id,
            decision_id=run.decision_id if run else None,
            epoch=run.epoch if run else None,
            payload=payload,
        )
        for observer in self.observers:
            observer(event)
        return event


class EnforcementMiddleware(Middleware):
    def __init__(self, gateway: Gateway) -> None:
        self.gateway = gateway

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        gw = self.gateway
        spec = self._spec(context.message.name)
        run = self._run(context)
        call = ToolCall(
            run_id=run.id if run else None,
            actor=run.actor if run else None,
            tool=spec,
            args=dict(context.message.arguments or {}),
        )
        verdict: Verdict = enforce(call, gw.state)

        if verdict.outcome == "reject":
            gw.record_call(call, "rejected", reason=verdict.reason)
            raise ToolError(str(verdict.reason))

        if verdict.outcome == "queue" and run is not None:
            action = gw.queue_send(call, run)
            return ToolResult(structured_content={"queued": action.id})

        token = CALLER.set(call.actor or "unknown")
        try:
            result = await call_next(context)
        except ToolError as exc:
            gw.record_call(call, "failed", reason=str(exc))
            raise
        finally:
            CALLER.reset(token)
        gw.record_call(call, "executed", result=result.structured_content)
        return result

    def _spec(self, wire_name: str) -> ToolSpec:
        try:
            return self.gateway.catalogue.by_wire(wire_name)
        except KeyError:
            raise ToolError(f"unknown_tool: {wire_name}") from None

    def _run(self, context: MiddlewareContext[mt.CallToolRequestParams]) -> RunState | None:
        fctx = context.fastmcp_context
        if fctx is None:
            return None
        params = fctx.session.client_params
        if params is None:
            return None
        return self.gateway.run_for_connection(params.clientInfo.name)
