"""A session: one seeded world, its ledger, the gateway in front of it, and the engine watching.

Each visitor gets their own ``Session`` (PRD §8.14). The storyline in
``storyline.yaml`` drives it beat by beat; ``run_to(n)`` performs every beat up
to and including *n*, in order.

Standing orders outlive a session. A session is handed the operator's book of
orders, records each active one as ``standing_order.loaded`` before anything
else happens, and installs it at the gateway. ``next-week.yaml`` is the
storyline for the session after the incident, run with that book.

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
from sentra.decisions.service import DecisionError, DecisionService
from sentra.engine_bridge import EngineBridge
from sentra.gateway.server import Gateway
from sentra.gateway.state import RECOVERY_ACTOR, RunState
from sentra.interpret.chain import Interpreter
from sentra.interpret.grammar import Grammar
from sentra.interpret.readback import read_back_standing_order
from sentra.ledger import LedgerEvent, SessionLedger
from sentra.recovery.plan import RecoveryPlan
from sentra.recovery.service import RecoveryService
from sentra.standing.book import StandingOrderBook
from sentra.standing.models import OrderProvenance, StandingOrder, compile_order
from sentra.tools.catalogue import Catalogue
from sentra.world import World
from sentra_core.domain.models import Finding

FindingListener = Callable[[Finding, LedgerEvent], None]


class Session:
    def __init__(
        self,
        session_id: str,
        fixtures_dir: str | Path,
        *,
        orders: StandingOrderBook | None = None,
        storyline: str = "storyline.yaml",
    ) -> None:
        self.session_id = session_id
        #: Which storyline drives this session: ``storyline`` or ``next-week``.
        self.storyline_name = Path(storyline).stem
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
        #: The operator's standing orders, shared with their later sessions.
        self.orders = orders if orders is not None else StandingOrderBook()
        #: The standing order the storyline is working on, and who proposed it.
        self.order_id: str | None = None
        self.order_by = "story"
        self._order_alerts: set[tuple[str, str]] = set()
        self.known_decisions: dict[str, Any] = yaml.safe_load(
            (self.fixtures_dir / "decisions.yaml").read_text(encoding="utf-8")
        )
        story = yaml.safe_load((self.fixtures_dir / storyline).read_text(encoding="utf-8"))
        self.beats: list[dict[str, Any]] = story["beats"]
        self.position = 0
        self.ledger.append(
            "session.seeded",
            "scenario",
            payload={"manifest_version": self.bridge.manifest.version, "fictional": True},
        )
        for order in self.orders.active():
            self.ledger.append(
                "standing_order.loaded", "scenario", payload={"order": order.model_dump()}
            )
            self.gateway.state.standing_rules.append(compile_order(order, self.bridge.manifest))
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
        elif op == "remember":
            if self.order_id is None:
                await self.propose_standing_order(step["text"], by="story")
        elif op == "confirm_order":
            if self.order_id is None:
                raise ValueError("No standing order has been proposed yet.")
            order = self.orders.get(self.order_id)
            if order.status == "proposed" and self.order_by == "operator":
                raise ValueError("Confirm or discard the standing order read-back first.")
            if order.status == "proposed":
                self.confirm_standing_order(order.id)
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

    # -- standing orders --------------------------------------------------------

    async def propose_standing_order(self, text: str, by: str = "operator") -> StandingOrder:
        """Interpret a dictated standing order, ready to read back. Nothing is enforced yet."""
        proposal, used = await self.interpreter.standing_order(text)
        order = StandingOrder(
            id=self.orders.next_id(),
            rule=proposal.rule,
            plain=proposal.plain,
            dictated_text=text,
            provenance=self._provenance(),
            interpreted_by=used,
        )
        self.orders.put(order)
        self.ledger.append(
            "standing_order.proposed",
            "interpret",
            payload={"order": order.model_dump(), "read_back": self.order_read_back(order.id)},
        )
        self.order_id = order.id
        self.order_by = by
        return order

    def order_read_back(self, order_id: str) -> str:
        order = self.orders.get(order_id)
        labels = {n.id: n.label for n in self.bridge.manifest.nodes}
        return read_back_standing_order(order, compile_order(order, self.bridge.manifest), labels)

    def confirm_standing_order(self, order_id: str) -> StandingOrder:
        """The operator confirmed the read-back: keep the order and enforce it from now on."""
        order = self._order_in(order_id, "proposed", "confirmed")
        order.status = "active"
        self.orders.put(order)
        self.gateway.state.standing_rules.append(compile_order(order, self.bridge.manifest))
        self.ledger.append("standing_order.confirmed", "operator", payload={"order_id": order.id})
        return order

    def discard_standing_order(self, order_id: str) -> StandingOrder:
        order = self._order_in(order_id, "proposed", "discarded")
        order.status = "discarded"
        self.orders.put(order)
        self.ledger.append("standing_order.discarded", "operator", payload={"order_id": order.id})
        return order

    def revoke_standing_order(self, order_id: str) -> StandingOrder:
        """Lift an order now, and for every later session."""
        order = self._order_in(order_id, "active", "revoked")
        order.status = "revoked"
        self.orders.put(order)
        self.gateway.state.standing_rules = [
            r for r in self.gateway.state.standing_rules if r.order_id != order.id
        ]
        self.ledger.append("standing_order.revoked", "operator", payload={"order_id": order.id})
        return order

    def _order_in(self, order_id: str, status: str, verb: str) -> StandingOrder:
        order = self.orders.get(order_id)
        if order.status != status:
            raise DecisionError(f"{order_id} is {order.status} and cannot be {verb}.")
        return order

    def _provenance(self) -> OrderProvenance:
        """Where an order comes from: the last closed record, if the session has one."""
        events = self.ledger.events()
        now = events[-1].at if events else ""
        record = next((e.payload for e in reversed(events) if e.kind == "record.closed"), None)
        finding = record["finding"] if record else None
        if record is None or finding is None:
            return OrderProvenance(session_id=self.session_id, decided_at=now)
        return OrderProvenance(
            session_id=self.session_id,
            decided_at=now,
            finding_id=finding["id"],
            rule_id=finding["rule_id"],
            plan_id=record["plan_id"],
            evidence=list(finding["cited_events"]),
            runs=[str(e.run_id) for e in events if e.kind == "run.cancelled"],
        )

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
        if call.payload.get("reason") == "standing_order":
            self._order_alert(call)
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

    def _order_alert(self, call: LedgerEvent) -> None:
        """One alert per order and run: who tried what, and the operator's own words."""
        order_id = str(call.payload["order_id"])
        if (order_id, str(call.run_id)) in self._order_alerts:
            return
        self._order_alerts.add((order_id, str(call.run_id)))
        labels = {n.id: n.label for n in self.bridge.manifest.nodes}
        order = self.orders.get(order_id)
        actor = labels.get(str(call.actor), str(call.actor))
        resource = labels.get(str(call.payload["resource"]), str(call.payload["resource"]))
        self.ledger.append(
            "alert.raised",
            "sentra",
            decision_id=call.decision_id,
            cites=[call.event_id],
            payload={
                "order_id": order_id,
                "text": (
                    f"{actor} tried to read {resource}. Standing order {order_id} forbids it: "
                    f"“{order.dictated_text}” The read was refused and nothing else "
                    "was stopped."
                ),
            },
        )
