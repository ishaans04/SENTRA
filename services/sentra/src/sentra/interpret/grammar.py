"""The deterministic grammar: the last link of the interpretation chain.

With the model off, it is the whole of the chain.

It understands the storyline's phrasings and the hint list, as Wispr Flow types
them: with capitals, commas, a full stop and the occasional "okay, so" in front.
Text is normalised, then matched against ``grammar.yaml``. Every name it can
return comes from the manifest, so it cannot invent a resource or an agent.

A phrase it does not recognise returns ``None``. The caller says so and asks the
operator to rephrase or type; it never guesses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from sentra.conditions.predicates import ReadsOnlyFrom
from sentra.decisions.models import ConditionProposal, DecisionProposal
from sentra.recovery.plan import (
    ApplyControl,
    CancelRun,
    HoldAction,
    PlanStep,
    Preserve,
    Rebuild,
    RevokeAccess,
    grant_call_for,
)

if TYPE_CHECKING:
    from sentra.gateway.state import RunState
    from sentra.scenario import Session

_PUNCTUATION = re.compile(r"[^\w\s/-]+")
_SELF = ("it", "this agent", "the agent", "agent")
_POSSESSIVE = ("its", "their", "the agents", "this agents")
_CLAUSES = re.compile(r"[.,;!?]+|\band\b", re.IGNORECASE)


def normalise(
    text: str, fillers: frozenset[str] = frozenset(), anywhere: frozenset[str] = frozenset()
) -> str:
    words = [w for w in _PUNCTUATION.sub(" ", text.lower()).split() if w not in anywhere]
    while words and words[0] in fillers:
        words.pop(0)
    return " ".join(words)


#: Words that may follow a confirmation without changing what it means.
_CONFIRM_TAIL = frozenset({"please", "go", "ahead", "run", "it", "do", "now", "thanks", "yes"})


def _strip_article(phrase: str) -> str:
    for article in ("the ", "a ", "an "):
        if phrase.startswith(article):
            return phrase[len(article) :]
    return phrase


@dataclass(frozen=True)
class Grammar:
    rules: dict[str, Any]
    labels: dict[str, str]

    @classmethod
    def load(cls, fixtures_dir: str | Path) -> Grammar:
        root = Path(fixtures_dir)
        rules = yaml.safe_load((root / "grammar.yaml").read_text(encoding="utf-8"))
        manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
        labels = {node["id"]: node["label"] for node in manifest["nodes"]}
        return cls(rules=rules, labels=labels)

    @property
    def fillers(self) -> frozenset[str]:
        return frozenset(self.rules.get("fillers", []))

    def normalise(self, text: str) -> str:
        anywhere = frozenset(self.rules.get("fillers_anywhere", []))
        return normalise(text, self.fillers, anywhere)

    # -- names ----------------------------------------------------------------

    def resource(self, phrase: str) -> str | None:
        phrase = _strip_article(phrase.strip())
        for resource_id, spec in self.rules["resources"].items():
            if phrase == resource_id or phrase in spec["phrases"]:
                return str(resource_id)
        return None

    def resources(self, phrase: str) -> list[str] | None:
        parts = re.split(r"\s+(?:and|or)\s+", phrase.strip())
        found = [self.resource(part) for part in parts]
        if not found or any(r is None for r in found):
            return None
        return [r for r in found if r is not None]

    def agent(self, phrase: str, default: str) -> str | None:
        phrase = phrase.strip()
        if phrase in _SELF or _strip_article(phrase) in _SELF:
            return default
        resolved = self.rules["agents"].get(_strip_article(phrase))
        return str(resolved) if resolved else None

    def plain(self, resource_id: str) -> str:
        return str(self.rules["resources"][resource_id]["plain"])

    # -- approvals ------------------------------------------------------------

    def parse_approval(self, text: str) -> DecisionProposal | None:
        """``approve <subject> [<opener> <agent> only reads from <resources>]``."""
        words = self.normalise(text)
        match = re.match(r"^approve (?P<subject>\w+)(?: work| runs?)?(?: (?P<rest>.*))?$", words)
        if not match:
            return None
        subject = self.rules["subjects"].get(match["subject"])
        if subject is None:
            return None
        proposal = DecisionProposal(
            statement=subject["statement"], subject=subject["subject"], actor=subject["actor"]
        )
        rest = match["rest"]
        if not rest:
            return proposal
        openers = sorted(self.rules["condition_openers"], key=len, reverse=True)
        opener = next((o for o in openers if rest.startswith(o + " ")), None)
        if opener is None:
            return None
        clause = re.match(
            r"^(?P<agent>.+?) only reads from (?P<resources>.+)$", rest[len(opener) + 1 :]
        )
        if not clause:
            return None
        actor = self.agent(clause["agent"], default=subject["actor"])
        resources = self.resources(clause["resources"])
        if actor is None or actor != subject["actor"] or resources is None:
            return None
        plain = "this agent receives only " + " and ".join(self.plain(r) for r in resources)
        proposal.conditions.append(
            ConditionProposal(
                predicate=ReadsOnlyFrom(actor=actor, resources=resources), plain=plain
            )
        )
        return proposal

    # -- confirmations --------------------------------------------------------

    def is_confirmation(self, text: str) -> bool:
        """True for a short spoken yes ("Confirm", "Yes, run it") to a pending read-back."""
        words = self.normalise(text).split()
        phrases = sorted(
            (str(p).split() for p in self.rules.get("confirmations", [])), key=len, reverse=True
        )
        for phrase in phrases:
            if words[: len(phrase)] == phrase:
                return all(word in _CONFIRM_TAIL for word in words[len(phrase) :])
        return False

    # -- recovery -------------------------------------------------------------

    def parse_recovery(self, text: str, session: Session) -> list[PlanStep] | None:
        """One clause per step: cancel, cut, rebuild, keep or hold.

        "its" refers to the run named in an earlier clause, so "stop this reporting
        run, remove its scratchpad access" cuts the Reporting Agent's access. Any
        clause that is not one of these returns ``None`` for the whole instruction:
        a half-understood plan is not read back.
        """
        verbs: dict[str, list[str]] = self.rules["recovery"]
        steps: list[PlanStep] = []
        focus: RunState | None = None
        for raw in _CLAUSES.split(text):
            clause = self.normalise(raw)
            if not clause:
                continue
            verb, _, rest = clause.partition(" ")
            family = next((f for f, words in verbs.items() if verb in words), None)
            if family == "cancel":
                focus = self._run(rest, session)
                if focus is None:
                    return None
                steps.append(CancelRun(run_id=focus.id))
            elif family == "cut":
                cut = self._cut(rest, focus, session)
                if cut is None:
                    return None
                steps.extend(cut)
            elif family == "rebuild":
                rebuild = self._rebuild(rest, focus)
                if rebuild is None:
                    return None
                steps.append(rebuild)
            elif family == "keep":
                actor = self._kept(rest)
                if actor is None:
                    return None
                steps.append(Preserve(scope=actor))
            elif family == "hold" and focus is not None:
                steps.extend(
                    HoldAction(action_id=a.id)
                    for a in session.gateway.outbox.for_run(focus.id)
                    if a.status == "queued"
                )
            else:
                return None
        return steps or None

    def _run(self, phrase: str, session: Session) -> RunState | None:
        runs = session.gateway.state.runs
        for run_id, run in runs.items():
            if run_id.lower() in phrase.split():
                return run
        subject = next((s for s in self.rules["subjects"] if s in phrase.split()), None)
        actor = self.rules["subjects"][subject]["actor"] if subject else None
        candidates = [
            r
            for r in runs.values()
            if r.status in {"running", "stale"}
            and (actor is None or r.actor == actor)
            and r.decision_id
        ]
        if actor is None:
            candidates = [r for r in candidates if r.status == "stale"]
        candidates.sort(key=lambda r: (r.status != "stale", -list(runs).index(r.id)))
        return candidates[0] if candidates else None

    def _cut(self, phrase: str, focus: RunState | None, session: Session) -> list[PlanStep] | None:
        resource = None
        for resource_id, spec in self.rules["resources"].items():
            if any(p in phrase for p in sorted(spec["phrases"], key=len, reverse=True)):
                resource = str(resource_id)
                break
        if resource is None:
            return None
        actor = focus.actor if focus else None
        named = [a for p, a in self.rules["agents"].items() if p in phrase]
        if named and not any(phrase.startswith(p) for p in _POSSESSIVE):
            actor = str(named[0])
        if actor is None:
            return None
        steps: list[PlanStep] = []
        control = self._control_for(actor, resource, session)
        if control is not None:
            steps.append(ApplyControl(control_id=control))
        revoke = RevokeAccess(actor=actor, resource=resource)
        if grant_call_for(session, revoke) is not None:
            steps.append(revoke)
        return steps or None

    def _control_for(self, actor: str, resource: str, session: Session) -> str | None:
        manifest = session.bridge.manifest
        findings = session.bridge.open_findings()
        if findings:
            plan = session.bridge.plan(findings[0].id)
            recommended = next(
                (
                    c
                    for c in manifest.control_capabilities
                    if c.id == plan.recommended_capability_id
                ),
                None,
            )
            if recommended is not None and recommended.target == resource:
                return recommended.id
            viable = {c.capability_id for c in plan.candidates if c.viable}
        else:
            viable = {c.id for c in manifest.control_capabilities}
        for capability in sorted(manifest.control_capabilities, key=lambda c: c.cost):
            if (
                capability.id in viable
                and capability.target == resource
                and (capability.type == "quarantine_node" or capability.source == actor)
            ):
                return capability.id
        return None

    def _rebuild(self, phrase: str, focus: RunState | None) -> Rebuild | None:
        match = re.match(r"^(?:.*?\s)?(?:from|using|with) (?P<sources>.+)$", phrase)
        if not match or focus is None:
            return None
        sources = self.resources(match["sources"])
        if sources is None:
            return None
        return Rebuild(decision_id=focus.decision_id, sources=sources)

    def _kept(self, phrase: str) -> str | None:
        words = _strip_article(phrase.removeprefix("all ")).split()
        subject = self.rules["subjects"].get(words[0]) if words else None
        return str(subject["actor"]) if subject else None
