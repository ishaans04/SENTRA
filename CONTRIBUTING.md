# Contributing to HIVE

HIVE is a security-sensitive prototype. Every contribution must strengthen the ability to explain, reproduce, and safely contain a finding.

## Before editing

1. Read the README. It describes what the system actually claims and what it deliberately does not.
2. Choose one bounded task. Do not combine a schema change, a detector change and a console redesign in one change.
3. Check whether the change crosses a contract boundary in `contracts/`.
4. Use fictional data and simulated controls only.

## Dependency direction

```text
console -> generated/API contracts -> core API/application -> domain
core adapters -> application -> domain
fixtures/tests -> public contracts/domain
```

The domain must not import FastAPI, a graph library, a connector, or console code. The console must not re-implement policy or risk logic — it renders what the core concluded and never computes a security conclusion of its own.

## Change rules

- Add or update a deterministic test before changing security semantics. If a change makes a claim, a test must fail when the claim stops being true.
- Treat an event, manifest, finding, containment plan, or policy as a versioned contract.
- Add dependencies only with a written purpose, licence check, and local/offline fallback assessment.
- Never commit `.env` files, live endpoints, credentials, personal data, or real customer telemetry.
- Keep the first working security path smaller than the full platform vision.

## Quality gate

```bash
cd services/core && uv run ruff format --check src tests && uv run ruff check src tests && uv run mypy && uv run pytest -q
cd apps/console  && pnpm run check && pnpm run build && pnpm run test:e2e
```

Regenerate the derived artifacts if you changed the service or the fixtures:

```bash
cd services/core && uv run python -m hive_core.contract && uv run python -m hive_core.snapshot
```

CI runs all of the above and fails on any drift in the generated files.

## Review checklist

- [ ] The change has one clear owner and purpose.
- [ ] Safety claims are backed by an executable test or explicitly labelled future work.
- [ ] The UI does not invent or reinterpret a security conclusion.
- [ ] Error and empty states do not show a false "safe" or "contained" state.
- [ ] Documentation and contracts match the code.
