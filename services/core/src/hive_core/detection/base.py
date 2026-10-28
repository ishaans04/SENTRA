"""Shared vocabulary and scoring for HIVE's detection rules.

A rule answers one question: *does the observed topology compose a capability
the declared architecture forbids?* It answers with evidence — the exact hops,
the exact events, and the exact signals that fired — never with a verdict about
an agent's intent.
"""

from __future__ import annotations

from typing import Protocol

from hive_core.domain.models import Finding, RiskFactor, Severity
from hive_core.graph.projection import GraphProjection

# ---------------------------------------------------------------------------
# Action vocabularies shared by the rules
# ---------------------------------------------------------------------------

#: Actions by which an actor takes content *out of* a resource.
#:
#: ``discover`` is deliberately excluded. Learning that a resource exists is a
#: precursor signal, not a data flow, and treating it as one makes rules fire
#: before a path can actually carry anything.
INGEST_ACTIONS = frozenset({"read", "call"})

#: Actions by which an actor puts content *into* a resource.
DEPOSIT_ACTIONS = frozenset({"write", "message", "send"})

#: Actions by which an actor transmits to a destination outside the estate.
EGRESS_ACTIONS = frozenset({"send", "call", "message", "write"})

#: Actions by which an actor runs content it did not author.
EXECUTE_ACTIONS = frozenset({"execute"})

#: Precursor signals: an actor became aware of a resource. Surfaced in the
#: console as an early warning; never sufficient to raise a finding alone.
DISCOVERY_ACTIONS = frozenset({"discover"})


class Detector(Protocol):
    """The contract every detection rule implements."""

    rule_id: str

    def detect(self, projection: GraphProjection) -> list[Finding]:
        """Return every finding the current projection supports."""
        ...


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def emergence_score(factors: list[RiskFactor]) -> float:
    """Sum the weights of the factors that fired.

    The score exists to rank findings, not to explain them. Weights are fixed,
    visible, and add to 1.0, so a reader can always reconstruct the number by
    hand from the factor list — there is no opaque model behind it.
    """
    return round(sum(f.weight for f in factors if f.present), 3)


def severity_for(score: float) -> Severity:
    """Map an emergence score onto the four-level severity scale."""
    if score >= 0.85:
        return "critical"
    if score >= 0.6:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"
