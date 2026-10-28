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
from typing import Any

import yaml

from aegis.conditions.predicates import ReadsOnlyFrom
from aegis.decisions.models import ConditionProposal, DecisionProposal

_PUNCTUATION = re.compile(r"[^\w\s/-]+")
_SELF = ("it", "this agent", "the agent", "agent")


def normalise(text: str, fillers: frozenset[str] = frozenset()) -> str:
    words = _PUNCTUATION.sub(" ", text.lower()).split()
    while words and words[0] in fillers:
        words.pop(0)
    return " ".join(words)


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
        return normalise(text, self.fillers)

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
