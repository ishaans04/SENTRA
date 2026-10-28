---
title: HAEGIS
emoji: 🛡️
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Voice-guided containment and recovery for human–AI teams
---

# HAEGIS

**Voice-guided containment and recovery for human–AI teams.**

You approve an AI agent's work on a condition. Later, something changes: two agents that were each doing their job have composed a route nobody declared. HAEGIS finds the route, works out which approval it breaks, holds and rejects the affected agent calls at the tool gateway, and then lets you say how to recover in your own words. Nothing you dictate runs until you have read it back and confirmed it, and nothing a person edited by hand is ever overwritten.

- **Live sandbox:** link added when the Hugging Face Space is deployed
- **Recorded replay:** link added when GitHub Pages is deployed (the same story, labelled as a recording, with commands disabled)

Everything runs on fictional data. The tool servers are fictional and the webhook only counts deliveries; nothing outside the sandbox is contacted.

## The story the demo tells

1. **Approve.** "Approve reporting, on the condition that the Reporting Agent only reads from the approved, sanitized report store." It is read back as `ReadsOnlyFrom(reporting-agent, [report_store/approved_summaries])` and becomes approval D-1 at epoch 1.
2. **The agents work.** Support reads customer records and writes a sanitized summary. Reporting reads the summaries, writes a draft and queues an external send. A teammate edits the draft by hand.
3. **The route appears.** Support drops notes in an undeclared scratchpad and grants Reporting access, and Reporting reads it. HIVE's PS-001 rule finds a possible route from customer records to the external webhook and cites the four gateway calls it rests on.
4. **The approval falls.** The condition fails, D-1 is suspended at epoch 2, the queued send is held, and Reporting's retry is rejected at the gateway as `stale_epoch`.
5. **Recover, in your words.** "Stop this reporting run, remove its scratchpad access, and rebuild the report from approved summaries. Keep the support work." It is read back step by step, then run: cancel the run and its send, enforce the cheapest control that keeps declared work intact, revoke the grant, and correct the draft (which stops as a conflict, because a person edited it), then renew D-1 and start a fresh run.
6. **Check what actually happened.** Four checks measure the result: the route is closed, a probe from the stale run is rejected, the replacement finished from approved sources only, and preserved work and the human edit are unchanged. The final record reports all of it, the conflict included.

## How it works

```text
operator (Wispr Flow or keyboard) ──> console ──POST / SSE──> FastAPI (one process)
                                                               ├─ interpretation: Gemini → Groq → grammar (never on the enforcement path)
                                                               ├─ decision ledger: approvals, typed conditions, epochs
                                                               ├─ HIVE engine: graph, PS-001 / PS-002, containment planner
                                                               └─ MCP gateway (FastMCP) ──> fictional tool servers
                                                                  holds sends, rejects stale runs, enforces controls
```

- **One route to the tools.** Agents are MCP clients. Each connection is bound to one run, so identity comes from the connection, never from tool arguments.
- **Approval epochs are fencing tokens.** Suspending an approval moves its epoch forward, and the gateway rejects every call from a run that started under the old one.
- **Sends wait in an outbox** and are re-checked at release, so a withdrawn approval can stop a report already on its way.
- **Recovery is operation-specific.** Only registered inverses run, after a version check, under the recovery executor's own identity. Sends are irreversible and escalate.
- **No model on the enforcement path.** With `AEGIS_INTERPRETER=off` the whole storyline runs on the deterministic grammar and gives the same holds, rejections and recovery.
- **One ledger.** Every call, rejected ones included, is a ledger event, and replaying an exported ledger rebuilds identical state.

## Repository

```text
services/core/      the HIVE engine (ingest, graph, rules, containment planner), unchanged
services/aegis/     gateway, tool servers, decisions, conditions, recovery, interpretation, API
apps/console/       React console: live sandbox (judge path) and the HIVE engine view
fixtures/           the reporting estate: manifest, tools, decisions, grammar, storyline
contracts/          generated OpenAPI contracts
```

## Run it locally

Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 with pnpm. No API keys needed.

```bash
pnpm install && pnpm console:build
cd services/aegis && uv sync
AEGIS_INTERPRETER=off AEGIS_STATIC_DIR=../../apps/console/dist uv run uvicorn aegis.api.app:app --port 8765
```

Open <http://127.0.0.1:8765>. Set `GEMINI_API_KEY` (and optionally `GROQ_API_KEY`) and leave `AEGIS_INTERPRETER` unset to let a model interpret free-form instructions; the grammar is always the fallback.

| Variable | Meaning |
| --- | --- |
| `AEGIS_INTERPRETER` | `chain` (models, then grammar), `grammar`, or `off` (recordings and grammar only) |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | Free-tier keys; Space secrets in production |
| `AEGIS_GEMINI_MODEL` | Gemini model id, default `gemini-2.5-flash-lite` |
| `AEGIS_SESSION_CAP`, `AEGIS_SESSION_IDLE_MINUTES` | Sandbox limits (default 40 sessions, 30 minutes) |

## Tests

```bash
cd services/core  && uv run pytest -q          # HIVE engine
cd services/aegis && uv run pytest -q          # gateway, decisions, recovery, API, the whole storyline
pnpm console:check                             # console format, lint, types, Vitest
cd apps/console && pnpm test:e2e               # Playwright: HIVE journey and the typed judge path
```

## Wispr Flow

Every text box in the console is a plain field, so Wispr Flow types straight into it: the approval, the recovery instruction, corrections and the spoken "Confirm". The product never talks to Wispr and cannot tell dictated text from typed text, which is why every step also works by typing.

## Limits, stated up front

- A route is a risk finding, not proof that data left.
- Only calls through the gateway are controlled.
- Recovery uses only registered inverses and pre-authorised controls; an irreversible send that already went out is escalated, not "undone".
- A person's later edit is never overwritten. The conflict choices are keep the human version or leave it for review.

## Prior work

HAEGIS builds on HIVE (the population-level risk engine in `services/core`) and on the decision-model design of AEGIS. The gateway, decision ledger, hold and recovery mechanisms, interpretation layer and the Approvals and Recovery panels were built for this challenge; see the dated commits.

MIT licensed.
