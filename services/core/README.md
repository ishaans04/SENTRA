# HIVE core

The security analysis engine. Python 3.12, FastAPI, NetworkX, Pydantic v2.

Nothing here calls a model, reaches the network, or touches a real system.
Detection, planning and verification are deterministic code over checked-in
fictional fixtures.

## Run it

```bash
uv sync --group dev
uv run uvicorn hive_core.main:app --port 8000
```

`http://127.0.0.1:8000/docs` is the generated API reference.

## Check it

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy                       # strict over the product code
uv run pytest -q                  # 193 tests
```

## Regenerate what is derived

```bash
uv run python -m hive_core.contract   # contracts/openapi/hive-core-v1.json
uv run python -m hive_core.snapshot   # the console's recorded demo
```

Both are checked in, and CI fails if either has drifted from the code.

## Module map

Dependencies point inward. `domain/` imports nothing from the web, graph,
persistence or connector layers; everything else depends on it.

| Module | Owns |
| --- | --- |
| `domain/` | The typed security vocabulary and nothing else |
| `ingest/` | Validation, redaction and provenance — the trust boundary |
| `ledger/` | The append-only evidence log and its replay cursor |
| `graph/` | The MultiDiGraph projection, keyed by action, plus the data-flow orientation |
| `detection/` | PS-001, PS-002, and the shared weighted scoring |
| `containment/` | Counterfactual planning, and the single definition of what a control does |
| `policy/` | Manifest loading, validation, and invariant witnesses |
| `connectors/` | The simulated control point |
| `immunity/` | The reviewed pattern lifecycle |
| `lab/` | Scenario loading and synthetic population experiments |
| `application/` | Orchestration — the only layer that knows the order of operations |
| `api/` | Transport. No security decision is made here |

## Tests

| Path | Covers |
| --- | --- |
| `tests/unit/` | Each module's own guarantees, including the necessary-condition tests that make a rule go silent when any precondition is removed |
| `tests/integration/` | The operator journey over real HTTP |
| `tests/property/` | Invariants over arbitrary generated event streams |
| `tests/contract/` | The committed OpenAPI document and the shipped examples |
