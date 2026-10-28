"""A session: one seeded world, its ledger, the gateway in front of it, and HIVE watching.

Each visitor gets their own ``Session`` (PRD §8.14). The storyline in
``storyline.yaml`` drives it beat by beat; ``run_to(n)`` performs every beat up
to and including *n*, in order.

The session is also where a gateway call meets HIVE: every recorded call goes
to the bridge, and a new finding becomes ``finding.raised`` plus
``containment.proposed`` in the same ledger, citing the calls it rests on.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from aegis.agents.scripted import ScriptedAgent
from aegis.clock import LogicalClock
from aegis.decisions.models import Decision, DecisionProposal
from aegis.decisions.service import DecisionService
from aegis.gateway.server import Gateway
from aegis.hive_bridge import HiveBridge
from aegis.ledger import LedgerEvent, SessionLedger
from aegis.tools.catalogue import Catalogue
from aegis.world import World
from hive_core.domain.models import Finding

FindingListener = Callable[[Finding, LedgerEvent], None]


class Session:
    def __init__(self, session_id: str, fixtures_dir: str | Path) -> None:
        self.session_id = session_id
        self.fixtures_dir = Path(fixtures_dir)
        self.ledger = SessionLedger(session_id, LogicalClock())
        self.world = World.seed()
        self.catalogue = Catalogue.load(self.fixtures_dir / "tools.yaml")
        self.bridge = HiveBridge(self.fixtures_dir / "manifest.yaml")
        self.gateway = Gateway(self.world, self.ledger, self.catalogue)
        self.gateway.observers.append(self._on_call)
        self.decisions = DecisionService(self.ledger, self.bridge, self.gateway)
        self.gateway.observers.append(self.decisions.on_call)
        self.finding_listeners: list[FindingListener] = [self.decisions.on_finding]
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
        self.position += 1
        for step in beat["steps"]:
            await self._perform(step)
        return int(beat["n"])

    async def run_to(self, n: int) -> None:
        while not self.at_end and int(self.beats[self.position]["n"]) <= n:
            await self.step()

    def agent(self, run_id: str) -> ScriptedAgent:
        return ScriptedAgent(self.gateway, run_id)

    async def _perform(self, step: dict[str, Any]) -> None:
        op = step["op"]
        if op == "start_run":
            run = self.decisions.start_run(step["run"], step["decision"])
            if run.actor != step["actor"]:
                raise ValueError(f"{step['decision']} authorises {run.actor}, not {step['actor']}.")
        elif op == "approve":
            self.approve(step["text"])
        elif op == "call":
            await self.agent(step["run"]).call(step["tool"], step.get("args") or {})
        elif op == "human_edit":
            self.human_edit(step["item"], step["content"])
        else:
            raise ValueError(f"Unknown storyline op {op!r}.")

    # -- world actions --------------------------------------------------------

    def approve(self, text: str) -> Decision:
        """The operator dictates an approval and confirms its read-back."""
        decision = self.decisions.propose(self.interpret_approval(text), text)
        return self.decisions.confirm(decision.id)

    def interpret_approval(self, text: str) -> DecisionProposal:
        known = self.known_decisions["reporting_approval"]
        if " ".join(text.split()) != " ".join(str(known["dictated_text"]).split()):
            raise ValueError("That approval is not one this scenario knows.")
        return DecisionProposal(**known["proposal"])

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

    # -- HIVE -----------------------------------------------------------------

    def _on_call(self, call: LedgerEvent) -> None:
        for finding in self.bridge.observe(call):
            raised = self.ledger.append(
                "finding.raised",
                "hive",
                cites=list(finding.evidence_event_ids),
                payload=finding.model_dump(),
            )
            plan = self.bridge.plan(finding.id)
            self.ledger.append(
                "containment.proposed",
                "hive",
                cites=[raised.event_id],
                payload=plan.model_dump(),
            )
            for listener in self.finding_listeners:
                listener(finding, raised)
