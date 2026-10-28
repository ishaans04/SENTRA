# haegis (Python package)

The new half of HAEGIS: the MCP gateway, the fictional tool servers, the decision ledger, conditions, recovery, interpretation and the API. It depends on `hive-core` (in `../core`) by path and never edits it.

```bash
uv sync --group dev
uv run pytest -q
```
