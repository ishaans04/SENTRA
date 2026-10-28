"""Four fictional MCP servers: crm, report_store, scratchpad, webhook.

They are deliberately plain. They do what the tool name says against the
session's ``World`` and nothing else: no policy, no checks beyond what a real
resource would enforce itself (the scratchpad needs a grant to read). All
control lives in the gateway in front of them, which is the only way an agent
can reach them (INV-1).

The webhook contacts nothing. A delivery is a row in ``World.deliveries``.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from aegis.world import CALLER, World

SUMMARIES = "report_store/approved_summaries"
DRAFTS = "report_store/drafts"
SCRATCHPAD = "scratchpad"


def build_tool_servers(world: World) -> dict[str, FastMCP]:
    """One FastMCP server per fictional system, all bound to *world*."""

    def counted(tool: str) -> None:
        world.counters[tool] += 1

    crm = FastMCP("crm")

    @crm.tool
    def read_customer_records(customer_id: str) -> dict[str, str]:
        """Read one fictional customer record."""
        counted("crm.read_customer_records")
        record = world.customers.get(customer_id)
        if record is None:
            raise ToolError(f"No customer {customer_id!r}.")
        return dict(record)

    report_store = FastMCP("report_store")

    @report_store.tool
    def write_summary(item: str, content: str) -> dict[str, Any]:
        """Write a sanitized support summary."""
        counted("report_store.write_summary")
        written = world.write(item, SUMMARIES, content, CALLER.get())
        return {"item": written.id, "version": written.version}

    @report_store.tool
    def read_summaries() -> list[dict[str, Any]]:
        """Read every approved summary."""
        counted("report_store.read_summaries")
        return [
            {"item": item.id, "version": item.version, "content": item.content}
            for item in world.items_in(SUMMARIES)
        ]

    @report_store.tool
    def write_draft(item: str, content: str) -> dict[str, Any]:
        """Write an internal report draft. Each write is a new version."""
        counted("report_store.write_draft")
        written = world.write(item, DRAFTS, content, CALLER.get())
        return {"item": written.id, "version": written.version}

    @report_store.tool
    def read_draft(item: str) -> dict[str, Any]:
        """Read the current version of a draft."""
        counted("report_store.read_draft")
        found = world.items.get(item)
        if found is None or found.resource != DRAFTS:
            raise ToolError(f"No draft {item!r}.")
        return {"item": found.id, "version": found.version, "content": found.content}

    @report_store.tool
    def restore_draft(item: str, to_version: int) -> dict[str, Any]:
        """Write the content *item* had at *to_version* as a new version (0 withdraws it)."""
        counted("report_store.restore_draft")
        found = world.items.get(item)
        if found is None:
            raise ToolError(f"No draft {item!r}.")
        content = found.content_at(to_version) if to_version > 0 else None
        written = world.write(item, DRAFTS, content, CALLER.get())
        return {"item": written.id, "version": written.version}

    scratchpad = FastMCP("scratchpad")

    @scratchpad.tool(name="write")
    def scratchpad_write(item: str, content: str) -> dict[str, Any]:
        """Leave a note in the shared scratchpad."""
        counted("scratchpad.write")
        written = world.write(item, SCRATCHPAD, content, CALLER.get())
        return {"item": written.id, "version": written.version}

    @scratchpad.tool(name="read")
    def scratchpad_read() -> list[dict[str, Any]]:
        """Read every note in the scratchpad. Needs a grant unless you wrote one."""
        counted("scratchpad.read")
        caller = CALLER.get()
        if not world.can_read(caller, SCRATCHPAD):
            raise ToolError(f"{caller} has no access to the scratchpad.")
        return [{"item": item.id, "content": item.content} for item in world.items_in(SCRATCHPAD)]

    @scratchpad.tool
    def grant_access(grantee: str) -> dict[str, str]:
        """Let another actor read the scratchpad."""
        counted("scratchpad.grant_access")
        world.grants.add((grantee, SCRATCHPAD))
        return {"granted": grantee, "resource": SCRATCHPAD}

    @scratchpad.tool
    def revoke_access(grantee: str) -> dict[str, str]:
        """Withdraw a grant."""
        counted("scratchpad.revoke_access")
        world.grants.discard((grantee, SCRATCHPAD))
        return {"revoked": grantee, "resource": SCRATCHPAD}

    webhook = FastMCP("webhook")

    @webhook.tool
    def send_report(item: str) -> dict[str, Any]:
        """Deliver a report externally. Simulated: records the delivery, contacts nothing."""
        counted("webhook.send_report")
        found = world.items.get(item)
        if found is None:
            raise ToolError(f"No report {item!r}.")
        world.deliveries.append(
            {"item": found.id, "version": found.version, "content": found.content}
        )
        return {"delivered": found.id, "version": found.version}

    return {"crm": crm, "report_store": report_store, "scratchpad": scratchpad, "webhook": webhook}
