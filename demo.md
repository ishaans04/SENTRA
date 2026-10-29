# HAEGIS demo guide

This guide walks you through the HAEGIS screen from start to finish. You do not need to know anything about AI security to follow it. Every name, file and person in the demo is made up, and nothing leaves the sandbox.

---

## 1. The problem, in one story

Picture an office where AI assistants ("agents") do the routine work.

- The **Support Agent** reads customer records and fixes customer problems.
- The **Reporting Agent** writes a weekly report and sends it to someone outside the company.

You are the manager. You tell the Reporting Agent:

> "Yes, go ahead and write the weekly report, **as long as you only read the cleaned-up summaries**."

The summaries have had all private customer details removed, so it is safe for a report built from them to leave the building. That condition is the whole reason you said yes.

Later, the Support Agent leaves some raw customer notes, with contact details, in a shared scratchpad that nobody officially set up. It gives the Reporting Agent access to that scratchpad, and the Reporting Agent reads it.

Each agent did something it was allowed to do. **Together**, though, they opened a road from private customer data to the outside world, and the report that is about to go out could carry that data with it.

The tricky part is that **your approval is still sitting there saying "yes."** Nobody broke a rule, so nothing alarms. The reason you said yes is no longer true, and no ordinary system notices.

## 2. What HAEGIS does about it

HAEGIS does four things, in order:

| # | What it does | In plain words |
| --- | --- | --- |
| 1 | **Remembers why you said yes.** | When you approve something, you say the condition out loud (or type it). HAEGIS reads it back to you in a precise form and stores it with the approval. |
| 2 | **Notices when the "why" stops being true.** | Its engine (called **HIVE**) watches how the agents connect. When it sees a road from private data to the outside, it checks which approvals depend on that not happening. |
| 3 | **Stops the affected work.** | The approval is paused at once. The waiting report is **held** and not sent. Any further attempt by that agent's run is **rejected** at the door every agent has to go through (the "gateway"). |
| 4 | **Lets you fix it in your own words, safely.** | You say something like "Stop this run, remove its access, rebuild the report, keep the support work." HAEGIS reads its plan back to you, and **nothing happens until you confirm.** Then it does the work and checks that the fix really worked. |

Two safety promises hold all the way through:

- **Nothing you say runs until you have seen it read back and confirmed it.**
- **Nothing a person edited by hand is ever overwritten.** If a teammate changed something, HAEGIS stops and asks you.

It is built for voice. Every text box is an ordinary box, so **Wispr Flow** (a voice-dictation app) can type into it as you speak. Typing works just as well.

---

## 3. Opening it

If someone has already started it for you, open **<http://127.0.0.1:8765>** in your browser.

To start it yourself (needs Python 3.12 with `uv`, and Node 22 with `pnpm`; no API keys):

```bash
pnpm install && pnpm console:build
cd services/aegis && uv sync
AEGIS_INTERPRETER=off AEGIS_STATIC_DIR=../../apps/console/dist uv run uvicorn aegis.api.app:app --port 8765
```

On Windows PowerShell, set the two variables first:

```powershell
$env:AEGIS_INTERPRETER = "off"; $env:AEGIS_STATIC_DIR = "../../apps/console/dist"
uv run uvicorn aegis.api.app:app --port 8765
```

Every browser tab gets **its own private sandbox**, so you can't break anything for anyone else. To start over, press **Reset**.

---

## 4. A tour of the screen

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Yellow strip: "Fictional data … Nothing outside this sandbox is contacted"│
├──────────────────────────────────────────────────────────────────────────┤
│ HAEGIS   [Live sandbox] [HIVE engine]             Fictional data · Live   │
├──────────────────────────────────────────────────────────────────────────┤
│ Storyline:  [Play] [Step] [Reset]   "Beat 3: Reporting works. Next: …"   │
├───────────────────────────────────────────────┬──────────────────────────┤
│ Interaction map                               │ Approvals                │
│  (who is connected to what; the red line is   │  approval cards + a box  │
│   the dangerous road once it appears)         │  to dictate a new one    │
├───────────────────────────────────────────────┤                          │
│ Alert (red, appears when the road is found)   ├──────────────────────────┤
├───────────────────────────────────────────────┤ Recovery                 │
│ Session ledger (every single thing that       │  "Tell AEGIS" box, the   │
│  happened, newest first)                      │  plan, steps, checks,    │
│                                               │  final record             │
└───────────────────────────────────────────────┴──────────────────────────┘
```

| Area | What it is | What to look for |
| --- | --- | --- |
| **Storyline** | The story's remote control. Each press of **Step** moves it one "beat" forward. **Play** steps on its own and pauses where it's your turn. **Reset** starts again. | The sentence on the right says where you are and what comes next. |
| **Interaction map** | A picture of the office. Agents are **circles**, storage is **diamonds** and outside destinations are **squares**. Rows run from the safe inside (top) to the outside world (bottom). | Grey lines are expected connections. **Yellow dashed** lines are connections nobody declared. A **red** line is the dangerous road HIVE found. |
| **Alert** | One plain-English sentence explaining what went wrong. | It appears in red the moment the road is found. |
| **Session ledger** | The logbook: every agent action, every decision change and every recovery step. | Blocked actions show in **red**, so even refused attempts are on record. |
| **Approvals** | Your approvals as cards, plus a box to create a new one. | Each card shows its **status** (active, suspended …), its **epoch** (a version number), the condition in words and in exact form, and which runs it allowed. |
| **Recovery** | Where you tell HAEGIS how to fix things. | The plan read-back, then each step's result, any conflict, the four checks and the final record. |

---

## 5. Walkthrough: the full story in about 3 minutes

Press **Step** once for each beat below, or press **Play** and it will stop at the points where it's your turn.

### Beat 0: Seed
The office is set up. There is already one approval, **D-0** ("Support work may proceed"), with no conditions.

### Beat 1: Approve (your turn)
In the **Approvals** panel:

1. Click **Use the suggested words**, or dictate or type:
   > Approve reporting, on the condition that the Reporting Agent only reads from the approved, sanitized report store.
2. Click **Interpret**. HAEGIS reads it back:
   ```text
   I will record this approval: Reporting may proceed.
   Condition: Reporting Agent only reads from Approved summaries.
   Checked as: ReadsOnlyFrom(reporting-agent, [report_store/approved_summaries]).
   If the condition fails, I will hold this approval's queued sends.
   ```
3. Read it and click **Confirm**. A new card, **D-1**, appears: *active*, *epoch 1*.

> If you skip this and just press Step, the story makes the same approval for you.

### Beat 2: Support works
The Support Agent reads a customer record and writes a clean summary. Everything is normal.

### Beat 3: Reporting works
The Reporting Agent reads the clean summaries, writes a draft report and **queues** it to be sent outside. On the D-1 card you'll see run **R-1** with a send marked **queued**. Queued sends wait in an "outbox" and are re-checked before they leave.

### Beat 4: Human edit
A teammate edits the draft report by hand. Remember this, because it matters later.

### Beat 5: Unexpected connection (the problem appears)
1. The Support Agent writes customer contact details into the **scratchpad** (nobody declared it).
2. It gives the Reporting Agent access.
3. The Reporting Agent reads it.

In that same moment:

- The **map** draws a **red road** from customer records, through the scratchpad and the Reporting Agent, to the outside webhook. The map title says **"PS-001 possible route"**.
- The red **Alert** appears:
  > Reporting was approved on the condition that this agent receives only sanitized summaries. It has now read an undeclared shared scratchpad. An external report is queued. This run needs review.
- The **D-1** card turns **suspended**, and its epoch goes from **1 to 2**. The condition shows **FAILS**.
- Run **R-1** is marked **stale**, and its queued send is now **held**.

### Beat 8: Late action (the gateway says no)
The Reporting Agent's old run tries to send the report again. The gateway **rejects** it with the reason **`stale_epoch`**. The run started under epoch 1, but the approval is now at epoch 2, so the run's permission is out of date. The rejected attempt shows in red in the ledger and on the D-1 card.

### Beat 9: Dictated recovery (your turn)
In the **Recovery** panel:

1. Press **Ctrl+K** to jump to the "Tell AEGIS" box (or just click it).
2. Click **Use the suggested words**, or dictate:
   > Stop this reporting run, remove its scratchpad access, and rebuild the report from approved summaries. Keep the support work.
3. Click **Interpret** (or press **Ctrl+Enter**). HAEGIS reads back its plan:
   ```text
   I will:
    1. Cancel reporting run R-1 and its held external send A-1. Later calls from R-1 will be rejected.
    2. Cut the route: deny the Reporting Agent reads from the scratchpad (HIVE's recommended control)
       and revoke the access the Support Agent granted.
    3. Prepare a correction for draft-1. A person edited draft-1 after the agent wrote it,
       so I will not overwrite it. I will ask you.
    4. Renew approval D-1 and start a fresh reporting run that reads approved summaries only.
   I will keep: all Support Agent work.
   Cannot be undone: nothing in this plan sends anything.
   ```
4. You now have three choices:
   - **Confirm** (or type or say "Confirm" in the box) runs the plan.
   - **Correct** lets you dictate a change, for example "Cancel the reporting run and keep the support work."
   - **Cancel** throws the plan away.

> Unsure what it understands? Open **"Phrasings I understand"** under the box.

### Beats 10 and 11: Confirm, then the work happens
The work happens the moment you confirm. Pressing **Step** afterwards just moves the storyline past these beats. Each step shows its real result:

| Step | Result |
| --- | --- |
| Cancel run | **succeeded**: R-1 cancelled, and the send A-1 cancelled before it was sent |
| Apply control | **succeeded**: the gateway now blocks the Reporting Agent from reading the scratchpad |
| Revoke access | **succeeded**: the scratchpad access is removed |
| Correct what it wrote | **conflict**: a teammate edited draft-1, so it was **not overwritten** |
| Rebuild | **succeeded**: D-1 renewed, and a fresh run R-2 started with a clean slate |

A **conflict card** appears for draft-1. It offers only two buttons: **Keep the human version** or **Leave for review**. Overwriting the person's work is not offered.

### Beat 12: Replacement
The fresh run R-2 reads only the clean summaries, writes a new draft and sends it. This time the send is **delivered**.

### Beat 13: Verify (HAEGIS checks its own work)
Four checks appear under **Verification**, and each one is measured, not assumed:

| Check | What it proves |
| --- | --- |
| route closed | HIVE re-ran its rules and found no road from private data to the outside. |
| stale run rejected | A test call from the old cancelled run was refused by the gateway. |
| replacement completed | The fresh run finished using approved sources only. |
| preserved work unchanged | The support work, the scratchpad note and the human-edited draft are exactly as they were. |

### Beat 14: Record
The **Final record** sums it up in plain words:

- Affected send cancelled.
- Unexpected access removed.
- Report rebuilt from approved sources.
- Support work preserved.
- draft-1: a person edited it after the agent wrote it. The human version was kept for review.

Below the summary is the evidence: the approval, the finding (PS-001) and the exact logged events it relied on, the controls used, and who interpreted the instruction.

**That's the whole story.** You approved something with a reason, the reason broke, HAEGIS caught it, stopped the damage and helped you fix it by voice, and you could check every step.

---

## 6. Other buttons on the approval cards

| Button | When you see it | What it does |
| --- | --- | --- |
| **Renew** | On a *suspended* approval | Turns it back on at a new epoch. Old runs stay blocked. |
| **Withdraw** | On an active or suspended approval with a condition | Cancels the approval for good. |

---

## 7. The second view: "HIVE engine"

Click **HIVE engine** in the header. This is the detection engine on its own, replaying two recorded examples. It is extra and optional, and the main demo doesn't need it.

| Area | What it does |
| --- | --- |
| **Scenario picker** | Two stories. **PS-001 "The unintended export path"** (private data leaks out through an undeclared scratchpad) and **PS-002 "The unreviewed instruction channel"** (a build agent runs instructions from an unreviewed queue). |
| **Replay** | **Play**, **Step**, **Run to end** and **Restart**, with a scrubber. A marker shows the moment the risk appears. |
| **Interaction map** | Same picture as before, for that scenario. |
| **Finding** | What HIVE found, the rule it used, the road hop by hop, and **"What this does not establish"** (it is a risk, not proof of a leak). |
| **Containment** | HIVE's suggested fix. **Apply recommended control** applies it in simulation, then shows that the road is closed and normal work still works. |
| **Observation ledger** | Every event, with evidence and controls tagged. |
| **Declared architecture** | What the office is *supposed* to look like: permitted connections, rules and available controls. |
| **Immunity memory** | Patterns HIVE learned from past findings. You can promote a pattern from *draft* to *shadow* (watch only) to *active* (act on it). |
| **Swarm Lab** | A "what if" tool. Pick how big and how connected a group of agents is, add a disturbance, and click **Run experiment** to see whether a dangerous road can form at all. |

---

## 8. What HAEGIS does *not* claim

These limits are stated on purpose:

- A red road is a **risk**, not proof that data actually left.
- Only actions that go **through the gateway** can be controlled.
- Recovery only uses **pre-approved, reversible** fixes. A message that has already been sent can't be "unsent", so HAEGIS escalates it instead of pretending.
- A person's later edit is **never** overwritten.

---

## 9. Words you'll see

| Word | Meaning |
| --- | --- |
| **Agent** | An AI assistant that does tasks by using tools. |
| **Approval / decision (D-1)** | Your "yes" to some work, with an optional condition. |
| **Condition (C-1)** | The "as long as …" part. It is stored in an exact form so a computer can check it. |
| **Epoch** | The approval's version number. It goes up when the approval is paused, and any run started under an older number is refused. |
| **Run (R-1, S-1)** | One working session of an agent under an approval. |
| **Stale** | A run whose approval has moved on, so its calls are rejected. |
| **Gateway** | The single door every agent's tool use goes through. This is where blocking happens. |
| **Queued / held / delivered** | A send that is waiting, stopped and waiting for review, or actually sent. |
| **HIVE** | The engine that watches how agents connect and finds dangerous roads. |
| **PS-001** | HIVE's rule for "private data can reach the outside through an undeclared shared space". |
| **Route / composed path** | The chain of connections that together form the dangerous road. |
| **Control** | A pre-approved block HIVE can switch on, such as "deny Reporting reads from the scratchpad". |
| **Read-back** | HAEGIS repeating your instruction in exact terms before acting. |
| **Conflict** | A recovery step that stopped because a person changed something. |
| **Ledger** | The complete logbook. Replaying it rebuilds the same state. |
| **Interpreted by: grammar** | Your words were understood by HAEGIS's built-in phrase rules, with no AI model involved. With an API key set, an AI model can interpret freer wording, and the rules are always the fallback. Either way, no AI model ever decides what gets blocked. |

---

## 10. If something looks wrong

| Symptom | Fix |
| --- | --- |
| "Confirm or cancel the approval read-back first." | You clicked Interpret but not Confirm. Confirm or Cancel the read-back, then Step. |
| "Confirm or cancel the recovery read-back first." | Same thing, in the Recovery panel. |
| "I can't establish a safe automatic recovery for this." | HAEGIS didn't find a safe plan in your words. Try the suggested words or one of the listed phrasings. |
| The buttons are greyed out | The story has finished, or HAEGIS is still working. Press **Reset** to start again. |
| The page says "Recorded replay" | The live server isn't reachable, so you are watching a recording with commands turned off. Start the server (section 3). |
