---
title: SENTRA
emoji: 🛡️
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Voice-guided containment and recovery for human–AI teams
---

# SENTRA

**Stop what went wrong. Keep everything else.**

AI agents now do real work side by side: one answers support tickets, another writes the weekly report. Each step they take can be allowed on its own and still add up to something nobody approved, such as private customer details finding a way out of the company. The usual answer is to shut everything down. SENTRA stops only the work that became unsafe, repairs it, and leaves the rest running.

- **Site:** <https://ishaans04.github.io/SENTRA/>, the landing page, a guided walkthrough and the full console
- **Live service:** link added when the Hugging Face Space is deployed

Everything runs on fictional data. The tool servers are fictional and the webhook only counts deliveries; nothing outside the sandbox is contacted.

## What it does

| | |
| --- | --- |
| **Notices** | It sees when safe steps add up to an unsafe route, and shows exactly which steps did it. |
| **Pauses** | It remembers why each job was approved. When that reason stops being true, it pauses that job alone and holds anything it was about to send. |
| **Repairs** | You say how to recover in your own words. SENTRA reads them back as clear steps, runs nothing until you confirm, rebuilds the work the right way and never overwrites a change a person made. |

## The story the demo tells

1. **Approve.** "Approve reporting, on the condition that the Reporting Agent only reads from the approved, sanitized report store." It is read back as `ReadsOnlyFrom(reporting-agent, [report_store/approved_summaries])` and becomes an approval at epoch 1.
2. **The agents work.** Support reads customer records and writes a sanitized summary. Reporting reads the summaries, writes a draft and queues an external send. A teammate edits the draft by hand.
3. **The route appears.** Support drops notes in an undeclared scratchpad and grants Reporting access, and Reporting reads it. Rule PS-001 finds a possible route from customer records to the external webhook and cites the four calls it rests on.
4. **The approval falls.** The condition fails, the approval is suspended at epoch 2, the queued send is held, and Reporting's retry is rejected at the gateway as `stale_epoch`.
5. **Recover, in your words.** "Stop this reporting run, remove its scratchpad access, and rebuild the report from approved summaries. Keep the support work." It is read back step by step, then run: cancel the run and its send, enforce the cheapest control that keeps agreed work intact, revoke the grant, and correct the draft (which stops as a conflict, because a person edited it), then renew the approval and start a fresh run.
6. **Check what actually happened.** Four checks measure the result: the route is closed, a probe from the stale run is rejected, the replacement finished from approved sources only, and preserved work and the human edit are intact. The final record reports all of it, the conflict included.

## How it works

SENTRA has two parts that work together.

**The control engine** (`services/core`) keeps a picture of what each agent is allowed to reach and what it actually touched. It turns every observed call into a graph, runs the route rules (PS-001 and PS-002) over it, and plans containment: it tests each candidate control first and recommends the cheapest one that does not break agreed work.

**The gateway and decision layer** (`services/aegis`) sits between the agents and their tools. It records every approval with its condition, re-checks conditions as the engine reports findings, holds and rejects calls from runs whose approval has fallen, and carries out dictated recovery once you confirm the read-back.

```text
operator (Wispr Flow or keyboard) ──> site ──POST / SSE──> FastAPI (one process)
                                                           ├─ interpretation: Gemini → Groq → grammar (never on the enforcement path)
                                                           ├─ decision ledger: approvals, typed conditions, epochs
                                                           ├─ control engine: graph, PS-001 / PS-002, containment planner
                                                           └─ MCP gateway (FastMCP) ──> fictional tool servers
                                                              holds sends, rejects stale runs, enforces controls
```

- **One route to the tools.** Agents are MCP clients. Each connection is bound to one run, so identity comes from the connection, never from tool arguments.
- **Approval epochs are fencing tokens.** Suspending an approval moves its epoch forward, and the gateway rejects every call from a run that started under the old one.
- **Sends wait in an outbox** and are re-checked at release, so a withdrawn approval can stop a report already on its way.
- **Recovery is operation-specific.** Only registered inverses run, after a version check, under the recovery executor's own identity. Sends are irreversible and escalate.
- **No model on the enforcement path.** With interpretation off (`AEGIS_INTERPRETER=off`) the whole storyline runs on the deterministic grammar and gives the same holds, rejections and recovery.
- **One ledger.** Every call, rejected ones included, is a ledger event, and replaying an exported ledger rebuilds identical state.

## The site

| Address | Screen |
| --- | --- |
| `/` | Landing page: the idea in a few short sections, each with something to try |
| `/#/demo` | Guided walkthrough: the whole story in seven steps on one map |
| `/#/console` | Console: the recorded session as an operator sees it, with every event, approval and check |

The console plays a session recorded from the service, so the site works from any static host. [demo.md](demo.md) walks through every screen.

## Repository

```text
services/core/      control engine: ingest, graph, route rules, containment planner
services/aegis/     gateway, tool servers, decisions, conditions, recovery, interpretation, API
apps/console/       the site: landing page, guided walkthrough and console (React, Vite)
fixtures/           the reporting estate: manifest, tools, decisions, grammar, storyline
contracts/          generated OpenAPI contracts
```

## Run it locally

Python 3.12 with uv, Node 22 with pnpm. No API keys needed.

Just the site:

```bash
pnpm install && pnpm console:dev      # http://127.0.0.1:5173
```

The service, serving the built site:

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
cd services/core  && uv run pytest -q          # control engine
cd services/aegis && uv run pytest -q          # gateway, decisions, recovery, API, the whole storyline
pnpm console:check                             # site format, lint, types, Vitest
cd apps/console && pnpm test:e2e               # Playwright: landing, walkthrough and console in a real browser
```

## Wispr Flow

Every text box is a plain field, so Wispr Flow types straight into it: the approval, the recovery instruction, corrections and the spoken "Confirm". SENTRA never talks to Wispr and cannot tell dictated text from typed text, which is why every step also works by typing.

## Limits, stated up front

- A route is a risk finding, not proof that data left.
- Only calls through the gateway are controlled.
- Recovery uses only registered inverses and pre-authorised controls; an irreversible send that already went out is escalated, not "undone".
- A person's later edit is never overwritten. The conflict choices are keep the human version or leave it for review.

## Licence

MIT. See [LICENSE](LICENSE).
