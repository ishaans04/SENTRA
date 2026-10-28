"""Read-backs: what the system understood, in plain words, before anything runs.

Nothing dictated takes effect until the operator has seen this text and
confirmed it (INV-7). It is generated from the typed proposal, never by a
model, so what is read back is exactly what will run.
"""

from __future__ import annotations

from aegis.conditions.predicates import ManifestUnchanged, NoUndeclaredPath, ReadsOnlyFrom
from aegis.decisions.models import ConditionProposal, DecisionProposal

INTERPRETED_BY = {
    "grammar": "grammar (no model call)",
    "recorded": "recorded model response (no model call)",
    "gemini": "Gemini",
    "groq": "Groq",
}


def _label(labels: dict[str, str], node_id: str) -> str:
    return labels.get(node_id, node_id)


def describe_condition(condition: ConditionProposal, labels: dict[str, str]) -> tuple[str, str]:
    """The condition in words, and in its typed form."""
    p = condition.predicate
    if isinstance(p, ReadsOnlyFrom):
        sources = ", ".join(_label(labels, r) for r in p.resources)
        return (
            f"{_label(labels, p.actor)} only reads from {sources}",
            f"ReadsOnlyFrom({p.actor}, [{', '.join(p.resources)}])",
        )
    if isinstance(p, NoUndeclaredPath):
        return (
            f"no undeclared route from {_label(labels, p.source)} to {_label(labels, p.sink)}",
            f"NoUndeclaredPath({p.source}, {p.sink})",
        )
    assert isinstance(p, ManifestUnchanged)
    return (
        f"{_label(labels, p.actor)} uses only what the manifest declares",
        f"ManifestUnchanged({p.actor})",
    )


def read_back_decision(
    proposal: DecisionProposal, labels: dict[str, str], interpreted_by: str = "grammar"
) -> str:
    lines = [f"I will record this approval: {proposal.statement}."]
    for condition in proposal.conditions:
        words, typed = describe_condition(condition, labels)
        lines.append(f"Condition: {words}.")
        lines.append(f"Checked as: {typed}.")
    if not proposal.conditions:
        lines.append("Condition: none. This approval stands until you withdraw it.")
    if proposal.hold_rule:
        lines.append("If the condition fails, I will hold this approval's queued sends.")
    lines.append(f"Interpreted by: {INTERPRETED_BY.get(interpreted_by, interpreted_by)}")
    return "\n".join(lines)
