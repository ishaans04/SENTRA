# sentra (Python package)

The gateway and decision layer of SENTRA: the MCP gateway, the fictional tool servers, the decision ledger, conditions, recovery, interpretation and the API. It uses the control engine (`sentra-core`, in `../core`) as a path dependency.

```bash
uv sync --group dev
uv run pytest -q
```
