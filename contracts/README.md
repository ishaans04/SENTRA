# Contracts

The compatibility boundary between the console, the core service and anything
that integrates with either.

| Path | What it is |
| --- | --- |
| `openapi/hive-core-v1.json` | The core service's HTTP contract |
| `examples/valid_observation_event.json` | An observation the ingest boundary accepts |
| `examples/invalid_observation_event.json` | One it rejects, and why matters |

The OpenAPI document is **generated from the running service**, not maintained
by hand:

```bash
cd services/core && uv run python -m hive_core.contract
```

A contract test compares the committed file against a freshly generated one and
CI fails on any difference, so the spec in this repository is always the spec
the service implements. Both examples are exercised against the real validator
by that same suite — the valid one must parse, the invalid one must raise.
