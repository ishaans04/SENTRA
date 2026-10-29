"""A session: one seeded world, its ledger, the gateway in front of it, and the engine watching.

Each visitor gets their own ``Session`` (PRD §8.14). The storyline in
``storyline.yaml`` drives it beat by beat; ``run_to(n)`` performs every beat up
to and including *n*, in order.

The session is also where a gateway call meets the engine: every recorded call goes
to the bridge, and a new finding becomes ``finding.raised`` plus
``containment.proposed`` in the same ledger, citing the calls it rests on.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from sentra.agents.scripted import ScriptedAgent
from sentra.clock import LogicalClock
from sentra.decisions.models import Decision, DecisionProposal
from sentra.decisions.service import DecisionService
from sentra.engine_bridge import EngineBridge
from sentra.gateway.server import Gateway
from sentra.gateway.state import RECOVERY_ACTOR, RunState
from sentra.interpret.chain import Interpreter
from sentra.interpret.grammar import Grammar
from sentra.ledger import LedgerEvent, SessionLedger
from sentra.recovery.plan import RecoveryPlan
from sentra.recovery.service import RecoveryService
from sentra.tools.catalogue import Catalogue
from sentra.world import World
from sentra_core.domain.models import Finding

FindingListener = Callable[[Finding, LedgerEvent], None]


class Session:
    def __init__(self, session_id: str, fixtures_dir: str | Path) -> None:
        self.session_id = session_id
        self.fixtures_dir = Path(fixtures_dir)
        self.ledger = SessionLedger(session_id, LogicalClock())
        self.world = World.seed()
        self.catalogue = Catalogue.load(self.fixtures_dir / "tools.yaml")
        self.bridge = EngineBridge(self.fixtures_dir / "manifest.yaml")
        self.gateway = Gateway(self.world, self.ledger, self.catalogue)
        self.gateway.observers.append(self._on_call)
        self.decisions = DecisionService(self.ledger, self.bridge, self.gateway)
        self.gateway.observers.append(self.decisions.on_call)
        self.finding_listeners: list[FindingListener] = [self.decisions.on_finding]
        self.recovery = RecoveryService(self)
        self.grammar = Grammar.load(self.fixtures_dir)
        self.interpreter = Interpreter(self)
        #: The recovery plan the storyline is working on, once one is drafted.
        self.plan_id: str | None = None
        #: Who drafted it: the storyline may confirm its own plans, never the operator's.
        self.plan_by = "story"
        self.known_decisions: dict[str, Any] = yaml.safe_load(
            (self.fixtures_dir / "decisions.yaml").read_text(encoding="utf-8")
        )
        story = yaml.safe_load((self.fixtures_dir / "storyline.yaml").read_text(encoding="utf-8"))
        self.beats: list[dict[str, Any]] = story["beats"]
        self.position = 0
        self.ledger.append(
            "session.seeded",
            "scenario",
            payload={"manifest_version": self.bridge.manifest.version, "fictional": True},
        )
        for seeded in self.known_decisions["seeded"]:
            decision = self.decisions.propose(DecisionProposal(**seeded), "", producer="scenario")
            self.decisions.confirm(decision.id)

    # -- driving the storyline ------------------------------------------------

    @property
    def beat(self) -> int:
        """The number of the last beat performed, or -1 before the first."""
        return int(self.beats[self.position - 1]["n"]) if self.position else -1

    @property
    def at_end(self) -> bool:
        return self.position >= len(self.beats)

    async def step(self) -> int:
        """Perform the next beat and return its number."""
        if self.at_end:
            raise IndexError("The storyline has no more beats.")
        beat = self.beats[self.position]
        for step in beat["steps"]:
            await self._perform(step)
        self.position += 1
        return int(beat["n"])

    async def run_to(self, n: int) -> None:
        while not self.at_end and int(self.beats[self.position]["n"]) <= n:
            await self.step()

    def agent(self, run_id: str) -> ScriptedAgent:
        return ScriptedAgent(self.gateway, run_id)

    def recovery_agent(self) -> ScriptedAgent:
        """The recovery executor's own connection. Its identity is not an agent's."""
        if "X-1" not in self.gateway.state.runs:
            self.gateway.register_run(
                RunState(id="X-1", actor=RECOVERY_ACTOR, decision_id="", epoch=0)
            )
        return ScriptedAgent(self.gateway, "X-1")

    async def _perform(self, step: dict[str, Any]) -> None:
        op = step["op"]
        if op == "start_run":
            run = self.decisions.start_run(step["run"], step["decision"])
            if run.actor != step["actor"]:
                raise ValueError(f"{step['decision']} authorises {run.actor}, not {step['actor']}.")
        elif op == "approve":
            await self._storyline_approval(step["text"])
        elif op == "call":
            if step["run"] not in self.gateway.state.runs:
                raise ValueError(
                    f"Run {step['run']} does not exist: the recovery plan did not start a "
                    "replacement run. Reset to start the story again."
                )
            await self.agent(step["run"]).call(step["tool"], step.get("args") or {})
        elif op == "human_edit":
            self.human_edit(step["item"], step["content"])
        elif op == "recover":
            if self.plan_id is None:
                await self.recover(step["text"], by="story")
        elif op == "confirm_recovery":
            plan = self._plan()
            if plan.status == "read_back" and self.plan_by == "operator":
                raise ValueError("Confirm or cancel the recovery read-back first.")
            await self.recovery.confirm(plan.id)
        elif op == "release":
            await self.gateway.release_due()
        elif op == "complete_run":
            self.decisions.complete_run(step["run"])
        elif op == "verify":
            await self.recovery.verify(self._plan().id)
        elif op == "close_record":
            self.recovery.close_record(self._plan().id)
        else:
            raise ValueError(f"Unknown storyline op {op!r}.")

    # -- world actions --------------------------------------------------------

    async def propose_approval(self, text: str) -> Decision:
        """Interpret a dictated approval into a proposed decision, ready to read back."""
        proposal, _ = await self.interpreter.approval(text)
        return self.decisions.propose(proposal, text)

    async def approve(self, text: str) -> Decision:
        """The operator dictates an approval and confirms its read-back."""
        decision = await self.propose_approval(text)
        return self.decisions.confirm(decision.id)

    async def _storyline_approval(self, text: str) -> None:
        """Beat 1, unless the operator already dictated this approval at the console."""
        proposal, _ = await self.interpreter.approval(text)
        seeded = len(self.known_decisions["seeded"])
        existing = [d for d in self.decisions.all()[seeded:] if d.actor == proposal.actor]
        if not existing:
            await self.approve(text)
        elif existing[-1].status == "proposed":
            raise ValueError("Confirm or cancel the approval read-back first.")

    async def recover(self, text: str, by: str = "operator") -> RecoveryPlan:
        """Interpret a dictated recovery instruction into a plan, ready to read back."""
        steps, used = await self.interpreter.recovery(text)
        plan = self.recovery.draft(steps, text=text, interpreted_by=used)
        self.plan_id = plan.id
        self.plan_by = by
        return plan

    def _plan(self) -> RecoveryPlan:
        if self.plan_id is None:
            raise ValueError("No recovery plan has been drafted yet.")
        return self.recovery.get(self.plan_id)

    def human_edit(self, item_id: str, content: str) -> None:
        """A person edits an item by hand at the console. Writer: ``teammate``."""
        existing = self.world.items.get(item_id)
        if existing is None:
            raise KeyError(f"No item {item_id!r}.")
        item = self.world.write(item_id, existing.resource, content, "teammate")
        self.ledger.append(
            "item.version_changed",
            "human",
            actor="teammate",
            payload={"item": item.id, "version": item.version, "writer": "teammate"},
        )

    # -- Engine ---------------------------------------------------------------

    def _on_call(self, call: LedgerEvent) -> None:
        for finding in self.bridge.observe(call):
            raised = self.ledger.append(
                "finding.raised",
                "engine",
                cites=list(finding.evidence_event_ids),
                payload=finding.model_dump(),
            )
            plan = self.bridge.plan(finding.id)
            self.ledger.append(
                "containment.proposed",
                "engine",
                cites=[raised.event_id],
                payload=plan.model_dump(),
            )
            for listener in self.finding_listeners:
                listener(finding, raised)
