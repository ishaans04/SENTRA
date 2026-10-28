# One real result: the gateway in front of your own MCP servers

**Status: not run yet.** The tool is built and tested (`services/aegis/tests/test_real.py`). The run on your own servers, and its write-up below, is still to do. If it isn't done before submission, the submission should say so.

## What it does

`python -m aegis.real` puts a FastMCP proxy (`create_proxy`) in front of the real MCP servers in a standard MCP config. Every call through it is recorded in a ledger, with the caller taken from the MCP connection: your client's own name, never a tool argument. If you also describe your estate in a HIVE manifest and map your tools to effects and resources, each call goes to the HIVE engine and any finding is recorded.

It observes and records. It refuses a call only if you pass a `--deny actor:tool` rule, and then only for calls that go through the proxy. It never undoes anything on a real system.

## How to run it

```bash
cd services/aegis
uv run python -m aegis.real --config ~/path/to/mcp.json \
  --manifest ~/path/to/my-estate.yaml --tools ~/path/to/my-tools.yaml
```

- `mcp.json` is the usual `{"mcpServers": {...}}` file your client already uses.
- `my-tools.yaml` maps each tool to `{effect: read|write|send, resource: <manifest node id>}`. Tools you don't map are recorded as `unmapped` and are not fed to HIVE.
- Point your MCP client at this command (stdio) instead of at the servers directly, and work as usual.
- The ledger is written to `services/aegis/.local/real-result.jsonl`.

## Write-up (fill in after the run)

- **Servers and client used:**
- **What the gateway observed:** number of calls, by tool and outcome
- **Findings HIVE raised, if any:**
- **A short ledger excerpt** (fictional or redacted where needed):
- **Screenshot:**
