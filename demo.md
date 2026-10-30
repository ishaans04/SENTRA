# SENTRA demo guide

This guide walks you through SENTRA from the first page to the last. You do not need to know anything about AI security to follow it. Every name, file and person in the demo is made up, and nothing is sent anywhere.

SENTRA has three screens:

| Screen | What it is | How long |
| --- | --- | --- |
| **Landing page** | The idea in five short sections, each with something to click. | 2 minutes |
| **Guided walkthrough** | The whole story in eight simple steps, on one map. | 2 minutes |
| **Console** | The same story as an operator sees it: every event, every approval, every check. | 3–5 minutes |

---

## 1. The problem, in one story

Picture an office where AI assistants ("agents") do the routine work.

- The **Support agent** reads customer records and helps customers.
- The **Reporting agent** writes a weekly report and sends it to partners outside the company.

You are the manager. You tell the Reporting agent:

> "Yes, go ahead and send the weekly report, **as long as you only read the approved summaries**."

The summaries have had all private customer details removed, so a report built from them is safe to send out. That condition is the whole reason you said yes.

Later, the Support agent starts saving notes, including customer details, in a shared notepad that nobody planned for. Then the Reporting agent reads that notepad too.

Each agent did something it was allowed to do. **Together**, though, they opened a way for private customer details to leave the company, and the report that is about to go out could carry them.

The tricky part is that **your approval still says "yes."** Nobody broke a rule, so nothing alarms. The reason you said yes is no longer true, and no ordinary system notices.

## 2. What SENTRA does about it

| # | What it does | In plain words |
| --- | --- | --- |
| 1 | **Notices.** | It sees when safe steps add up to something unsafe, and shows you exactly which steps. |
| 2 | **Pauses.** | It remembers why you approved each job. When that reason stops being true, it pauses just that job. |
| 3 | **Repairs.** | You say what to do in your own words. It reads your words back as clear steps, and nothing happens until you confirm. Then it redoes the work the right way and never overwrites a change a person made. |
| 4 | **Remembers.** | You say what should always hold. It keeps that as a standing order, with the incident behind it, and refuses the same risky step in every later session. Only your confirmed words can write one. |

It is built for voice. The instruction box is an ordinary text box, so **Wispr Flow** (a voice-dictation app) can type into it as you speak. Typing works just as well.

---

## 3. Opening it

If someone has already started it for you, open **<http://127.0.0.1:8765>** (or the link you were given).

To start it yourself you need Node 22 and `pnpm`. No API keys, no accounts:

```bash
pnpm install
pnpm console:dev
```

Then open **<http://127.0.0.1:5173>**.

To run the production build instead:

```bash
pnpm console:build
pnpm --filter @sentra/console preview
```

Then open **<http://127.0.0.1:4173>**.

Each screen has its own address, so you can jump straight to one:

| Address ending | Screen |
| --- | --- |
| `/` | Landing page |
| `/#/demo` | Guided walkthrough |
| `/#/console` | Console |

---

## 4. The landing page

Scroll down slowly. The page is built to be scrolled: sections reveal as they arrive, and the problem section holds still while your scrolling plays it forward.

Three things stay with you the whole way down:

- A thin **blue line** along the top of the window fills as you read.
- On wide screens, a small **row of dots** floats on the right. Each dot is a section. Hover it to see the names, and click one to jump there.
- Soft colour drifts slowly behind the page as you scroll, so long stretches never look blank.

| Section | What you see | What to try |
| --- | --- | --- |
| **Top: "Stop what went wrong. Keep everything else."** | A field of dots. Each dot is an agent or something an agent uses. Every ten seconds a red chain of five links forms, one link is cut, and the rest turn green. | Move your cursor over the field: nearby dots link to it in blue. |
| **01 — The problem** | The section holds still while you scroll. Each scroll lights the next of four cards (**✓ Allowed**) and draws a line beneath them, with a large step counter on the right. At the end all four turn red, **Allowed · but linked**, and "private customer details now have **a way out**." | Scroll slowly, then back up to rewind. **↺ Play it again** takes you back to the start. |
| **02 — What SENTRA does** | **Notice**, **Pause**, **Repair** and **Remember**, each with its own small animation in a panel on the right. They take turns every few seconds. | Click a word to jump to it. Move your cursor over the panel: it tilts towards you. |
| **03 — You stay in charge** | A voice card, with small labels floating around it. | Tap the **mic**. Your words appear as if dictated, then SENTRA lists the four steps it will take. Click **Yes, do it** and watch each step tick off. |
| **04 — The difference** | Eight jobs that are all running, and a counter of how many are still working. | Click **Shut everything down**: every job stops and the counter drops to 0. Click **Use SENTRA**: only the weekly report pauses and gets redone, and the counter climbs back to 8. |
| **05 — Why not just an LLM?** | A dark panel that explains what SENTRA does that a general AI chatbot can't. See below. | Scroll through it. |
| **06 — Honest by design** | Three plain promises: a warning isn't proof, you approve the big moves, and some things can't be undone. | Read them. |

Cards light up softly wherever your cursor moves over them.

### 05 — Why not just an LLM?

This section answers the question people ask first: *"Couldn't I just use ChatGPT or Gemini for this?"* It has three parts.

1. **Ask both.** One situation, two answers, side by side: *"Reporting just read a notepad full of customer details. Its weekly report goes out in a minute."* A general AI assistant types out polite advice, and the report still goes out. SENTRA, using events from the recorded session, finds the route, withdraws the approval, **holds** the report and waits for you. The assistant's answer is marked **ILLUSTRATIVE**. Click **↺ Ask both again** to replay it.
2. **Three differences.** Three boxes, laid out like the reasons below them. Each sets what a plain LLM does against what SENTRA does:

   | Difference | A plain LLM | SENTRA |
   | --- | --- | --- |
   | Sees the whole system | Sees one conversation at a time. | Watches how every agent connects. |
   | Remembers why you said yes | Forgets the reason when the chat ends. | Keeps each approval's condition and re-checks it on every event. |
   | Acts, not just advises | Can suggest; can't stop anything. | Holds sends and rejects stale calls at the gateway. |

3. **Why teams choose it.** Four reasons: it's audit-ready by default, it works with the model off, it makes the smallest possible fix, and it sits in front of the MCP tool servers you already run. **See every step in the console** opens the console.

At the bottom, **Start the demo** opens the guided walkthrough and **Open the console** opens the console. Labels from the console ("HELD · H-2", "CONFIRMED #16" …) float around the headline and drift with your cursor. The same links are in the top bar (**Try the demo**, **Console**).

> On a small screen, or with your system set to reduce motion, the problem section plays as an ordinary section instead: its four cards light up on their own.

---

## 5. The guided walkthrough

A map of the office on the left, the story on the right. Press **Next →** or the **→** key to move on, and **←** to go back. **Esc** returns to the landing page. The bar along the top shows your step; click any segment to jump to it.

Shapes on the map: **circles** are agents, **rounded squares** are places data is kept, the **dashed square** is the notepad nobody planned for, and the **diamond** is the outside world. Click any shape to read what it is.

| Step | What happens |
| --- | --- |
| **1. Meet the team** | Two agents and your approval: "Reporting can send reports — because it only reads approved summaries." |
| **2. Something new shows up** | A yellow dashed line: Support starts using the shared notepad. SENTRA notes it, but nothing is wrong yet. |
| **3. The pieces line up** | Reporting reads the notepad too. A red path runs from customer info to the outside world, shown hop by hop. It's a *possible* path, not proof of a leak. |
| **4. The reason is gone** | Your approval is marked **NO LONGER TRUE**, and the weekly report is **paused** before it is sent. |
| **5. Tell SENTRA what to do** | Tap the mic (or press **Speak →**). Your instruction appears, read back as four steps. Press **Yes, do it**. |
| **6. Fixing only what's broken** | Five changes, one at a time: stop the old report, cut its access to the notepad, block a late send, rebuild the report from approved summaries, and keep Priya's edit. |
| **7. All clear** | Four green results. Press **Remember this →** to go on, **Watch again**, or go back home. |
| **8. Remember it for next time** | Press **Speak →**: *"From now on, an agent that can send outside never reads from a store nobody declared."* appears, with what SENTRA will keep. Press **Yes, keep it →**. Then **A week later**: Support's notes are still allowed, Reporting is turned away from the notepad citing your words, and the report goes out on time. From here you can **Watch again** or **Open the full console**. |

---

## 6. The console

The console replays one recorded session, event by event. It is the same story with all the detail an operator would need.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ SENTRA  ‹ ▶Play ›  1×   01 Approved · 02 Connection · … · 09 Next week    │
│                                                        [Tell SENTRA Ctrl K]│
├───────────────────────────────────────────────┬──────────────────────────┤
│ Chapter title and what it means               │ Case file                │
│                                 Current event │  Decision D-07           │
├───────────────────────────────────────────────┤  Finding PS-001          │
│ What the agents did (the map)                 │  Containment options     │
│                                               │  Tell SENTRA             │
├───────────────────────────────────────────────┤  Recovery steps          │
│ One ledger, three lanes + the latest events   │  Outcome record          │
└───────────────────────────────────────────────┴──────────────────────────┘
```

### The top bar

| Control | What it does |
| --- | --- |
| **‹ / ›** | One event back or forward. |
| **▶ Play** | Plays on its own. It always stops where it's your turn to decide, and at the end. |
| **1×** | Replay speed. Click to switch between 0.5×, 1× and 2×. |
| **01 … 09** | The nine chapters. The bar under each one fills as you go; click a chapter to jump to it. |
| **Tell SENTRA** | If you haven't reached your turn yet, jumps straight to it and puts the cursor in the instruction box. |
| **SENTRA** (left) | Back to the landing page. |

### The map: "What the agents did"

Bands run from the most private (top) to the outside world (bottom). **Grey lines** are connections everyone agreed to. **Yellow dashed** lines were seen but never declared. A **red** line is the dangerous route. Labels appear on the map as things happen ("route closes", "HELD", "send rejected", "read revoked"). Click any box to see what it is supposed to do and what it was actually seen doing.

### The ledger: "One ledger, three lanes"

Every event has one mark, in one of three lanes: **decisions** people made, what the **gateway** enforced (the single door every agent's actions pass through), and what the **agents** did. Click any mark to jump to that moment. Below the lanes are the six latest events, newest first. A strip at the bottom lists the keyboard shortcuts.

### The case file (right side)

| Card | What it shows |
| --- | --- |
| **Decision D-07** | Your approval, its condition in plain words and in exact form, its status, and every run made under it. |
| **Finding PS-001** | Appears when the route forms: the four hops, which ones were declared, and the evidence for each. It says plainly that a route is not proof of a leak. |
| **Containment** | Five pre-approved ways to cut the route. Each one is tested first. Two would also break work that was agreed, so they are rejected. The cheapest safe one is recommended. |
| **Tell SENTRA** | Your instruction box and the read-back. |
| **Recovery** | Each step of the fix and its real result. |
| **Outcome record** | The final summary and the four checks. |

For the first two chapters the case file (**What people approved, and why**, with Decision D-07) sits on the page beside the map. From chapter 3 on it lives only in the glass panel below.

### The glass case file

From chapter 3 (**Route**) onwards, the case file becomes a frosted-glass panel that **slides in from the right edge** of the window. It uses the right-hand column only, so the map and the ledger stay fully visible. It holds every card: what people approved and why (Decision D-07), the finding, the containment options, Tell SENTRA, the recovery steps and, at the end, the outcome record. None of it appears on the page itself any more, even while the panel is closed.

- As the story moves on, the panel **scrolls itself to what is happening now** and outlines that card in blue: the finding when the route forms, the decision while it is withdrawn, Tell SENTRA at your turn, and the recovery steps one by one while the fix runs.
- Close it with the **✕** at its top right, or press **Esc**. A small **Case file** tab then waits on the right edge; click it to bring the panel back.
- It slides back in on its own as each new stage starts (route found, **Withdrawn**, **Decide**, **Recover**), and the case file returns to the page if you step back before chapter 3.

---

## 7. Console walkthrough: the full story in about 3 minutes

Press **▶ Play**, or step through with **›**. The event counter at the top right goes from #07 to #28.

### Chapter 1: Approved

The approved workflow is running. **Decision D-07** is **VALID · EPOCH 3** (the epoch is the approval's version number). Run r-0411 has already delivered a report.

### Chapter 2: Connection

The Support agent starts writing to a scratchpad nobody declared (#08–#09). It appears on the map with a yellow dashed line and an **UNDECLARED** tag. No finding yet, because nothing has taken data out.

### Chapter 3: Route

The **glass case file slides in from the right**, carrying Decision D-07 with it. The Reporting agent finds the scratchpad (#10) and queues its next report, r-0412 (#11). Then it reads the scratchpad (#12). The red route lights up from the customer records, through the scratchpad and the Reporting agent, to the outside webhook. **Finding PS-001** and the **Containment** options appear.

### Chapter 4: Withdrawn

SENTRA links the finding to D-07. Its condition fails and no other reason to allow it exists, so D-07 shows **NEEDS REVIEW** (#13). The gateway then **holds** the queued report before it leaves, and D-07 reads **BASIS WITHDRAWN · RUN HELD** (#14).

### Chapter 5: Decide (your turn)

Playback stops here. The **Tell SENTRA** card is open, filled with the suggested instruction:

> Stop this reporting run, remove its scratchpad access, and rebuild the report from approved summaries. Keep the support work.

Under it, the **read-back** turns those words into four exact steps: cancel run r-0412, remove the Reporting agent's scratchpad access, rebuild the report as r-0413, and keep the support work. **Nothing runs until you confirm.**

You can dictate your own words with Wispr Flow, or type them. The read-back updates as you type, and steps you didn't ask for are greyed out. If your words ask for nothing, the confirm button stays disabled.

Press **Confirm read-back and run**, or **Ctrl+Enter** (**⌘+Enter** on a Mac). D-07 is renewed at **epoch 4** for the new run only (#16).

### Chapter 6: Recover

The glass case file moves to the **Recovery** card, which shows each step as it happens:

| Step | Result |
| --- | --- |
| Cancel run r-0412 | Done (#17). The old run then tries to send anyway, and the gateway **rejects** it, because it still carries epoch 3 (#19). |
| Remove scratchpad access | Done (#18). Only the read is cut. Support can still use its notes. |
| Rebuild from approved summaries | Fresh run r-0413 reads only the approved store (#20) and delivers the new report (#22). |
| Keep the support work | **Conflict** (#21): Priya edited the report draft after the agent wrote it. Her version is kept and she is asked to review. It is never overwritten. |

If you left a step out of your instruction, it shows as **not requested — left as it is**.

### Chapter 7: Verified

The rules run again over the contained setup (#23). The **Outcome record** pops up in the middle of the screen, with a short bar counting down. After three seconds it moves into the glass case file on the right (click **Move now**, click outside it, or press **Esc** to move it sooner). It lists four checks, each with its evidence:

| Check | What it proves |
| --- | --- |
| Route removed | The finding re-ran and found nothing. |
| Held action prevented | The old run's late send was rejected. |
| Replacement completed | The new report went out under epoch 4. |
| Unrelated work survived | Support's work and Priya's edit are untouched. |

Press **▶ Play** to go on, or **Replay from the start** to watch it again.

### Chapter 8: Remember (your turn again)

Play stops a second time. A **Remember for next time** card opens in the case file with the suggested words already in it:

> *From now on, an agent that can send outside never reads from a store nobody declared.*

You can dictate your own with Wispr Flow or type them. The read-back says what will be kept: standing order SO-1, checked as `NoUndeclaredReads(senders)`, because of PS-001 and run r-0412, holding in every later session until you revoke it (#24). Words that are not a standing order leave the button disabled. Press **Keep this standing order**, or **Ctrl+Enter** (#25).

### Chapter 9: Next week

The same work, a week later. Support saves notes to the scratchpad again (#26), which is still allowed: Support cannot send anything out. Reporting tries to read them and the gateway **refuses** that one read under **SO-1** (#27). No red route appears, no approval falls, and run r-0420 delivers the report on time (#28).

---

## 8. Keyboard shortcuts

| Keys | Where | What it does |
| --- | --- | --- |
| **→ / ←** | Walkthrough, console | Next / previous step or event |
| **Esc** | Walkthrough | Back to the landing page |
| **Esc** | Console | Close the glass case file (or send the outcome record into it) |
| **Space** | Console | Play / pause |
| **Ctrl+K** (⌘+K) | Console | Jump to Tell SENTRA |
| **Ctrl+Enter** (⌘+Enter) | Console | Confirm the read-back, or keep the standing order |
| **Enter** | Console, at your turn | Confirm the read-back, or keep the standing order |

---

## 9. "Gemini" and "Model off"

The **Tell SENTRA** card has a small **Gemini / Model off** switch. In the recorded session, the instruction was read by a language model (Gemini Flash-Lite), with SENTRA's built-in phrase rules as the fallback. Switch to **Model off** and the badge changes to say so, but every hold, rejection and recovery step is identical, because **no model ever decides what gets blocked.**

When you type your own words in the console, they are read by the built-in phrase rules in your browser, and the card says so.

---

## 10. What SENTRA does *not* claim

These limits are stated on purpose:

- A red route is a **risk**, not proof that data actually left.
- Only actions that go **through the gateway** can be stopped.
- Recovery only uses **pre-approved, reversible** fixes. A message that has already been sent can't be "unsent", so SENTRA says so plainly instead of pretending.
- A person's later edit is **never** overwritten.
- A standing order covers one thing: agents that can send outside reading storage nobody declared, through the gateway.
- The console is a **recorded replay of made-up data**, not a live system.

---

## 11. Words you'll see

| Word | Meaning |
| --- | --- |
| **Agent** | An AI assistant that does tasks by using tools. |
| **Decision (D-07)** | Your "yes" to some work, with a condition. |
| **Condition (C-07a)** | The "as long as …" part, stored in an exact form so a computer can check it. |
| **Standing order (SO-1)** | A rule you said should always hold, kept with the incident behind it and checked in every later session until you revoke it. |
| **Epoch** | The approval's version number. It goes up when the approval is renewed, and anything still carrying an older number is refused. |
| **Run (r-0411, r-0412, r-0413)** | One working session of an agent under an approval. |
| **Gateway** | The single door every agent's actions go through. This is where holding and blocking happen. |
| **Held / rejected / delivered** | Stopped and waiting, refused at the door, or actually sent. |
| **Finding (PS-001)** | SENTRA's rule for "private data can reach the outside through a shared space nobody declared". |
| **Route** | The chain of connections that together form the dangerous path. |
| **Control** | A pre-approved block, such as "stop Reporting reading the scratchpad". |
| **Read-back** | SENTRA repeating your instruction as exact steps before acting. |
| **Conflict** | A recovery step that stopped because a person had changed something. |
| **Ledger** | The complete logbook of what happened. |

---

## 12. If something looks wrong

| Symptom | Fix |
| --- | --- |
| The confirm button is greyed out | Your words didn't ask for any of the four steps. Try the suggested words, or include words like "stop", "remove access", "rebuild" or "keep". |
| The instruction box won't let you type | It only accepts input at your turn (chapter 5). Press **Tell SENTRA** to jump there. |
| Playback stopped by itself | It stops at your turn and at the end. Confirm the read-back, or press **↺ Replay**. |
| Fonts look plain | The page loads its fonts from the internet. Without a connection it falls back to system fonts, and everything still works. |
| The page is blank | Make sure you opened the address the server printed, and reload. |
