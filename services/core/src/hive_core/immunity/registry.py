"""Reviewed memory of contained behaviour.

When a finding is contained, HIVE records the *abstract* precondition pattern
that produced it — never the specific node names. "An actor that reads
restricted data deposits into unregistered shared state which another actor
withdraws from and transmits externally" is portable across estates; "Support
Agent wrote to the scratchpad" is not.

Patterns enter as ``draft`` and stay there. Promotion to ``shadow`` (report but
take no action) and then to ``active`` is an explicit human decision, recorded
with a timestamp. Nothing here promotes itself, because a system that silently
generalises from one incident into a standing rule is exactly the opaque
behaviour HIVE is arguing against.
"""

from __future__ import annotations

from hive_core.domain.models import Finding, ImmunityPattern

#: Legal lifecycle transitions. Promotion is one step at a time and reversible.
_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"shadow"},
    "shadow": {"active", "draft"},
    "active": {"shadow"},
}

#: The abstract precondition set recorded for each rule, in operator language.
_PRECONDITIONS: dict[str, list[str]] = {
    "PS-001": [
        "An actor holds read access to a restricted data source.",
        "A shared resource exists that the architecture manifest does not declare.",
        "That actor deposits into the undeclared resource.",
        "A second actor withdraws from it and holds an external transmission capability.",
    ],
    "PS-002": [
        "A shared resource exists that the architecture manifest does not declare.",
        "One actor deposits content into it.",
        "A different actor executes content from it.",
        "The depositing actor ingests from an untrusted or external source.",
    ],
}

_CONTROL_CLASSES: dict[str, str] = {
    "PS-001": "block_deposit_into_undeclared_shared_state",
    "PS-002": "block_execution_from_undeclared_shared_state",
}


class LifecycleError(ValueError):
    """Raised on an illegal lifecycle transition."""


class ImmunityRegistry:
    """An in-memory store of reviewed behavioural patterns."""

    def __init__(self) -> None:
        self._patterns: dict[str, ImmunityPattern] = {}

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def record_from_finding(self, finding: Finding, recorded_at: str) -> ImmunityPattern:
        """Derive a draft pattern from a contained *finding*.

        *recorded_at* is the replay position the containment happened at, so a
        second replay of the same scenario produces an identical record.

        Recording the same finding twice returns the existing pattern rather
        than duplicating it, so replaying a scenario does not inflate the
        registry.
        """
        pattern_id = f"immunity-{finding.rule_id.lower()}"
        existing = self._patterns.get(pattern_id)
        if existing is not None:
            return existing

        pattern = ImmunityPattern(
            id=pattern_id,
            rule_id=finding.rule_id,
            lifecycle="draft",
            title=finding.title,
            abstract_preconditions=list(_PRECONDITIONS.get(finding.rule_id, [])),
            evidence_basis=list(finding.evidence_event_ids),
            recommended_control_class=_CONTROL_CLASSES.get(finding.rule_id, "unclassified"),
            created_at=recorded_at,
        )
        self._patterns[pattern.id] = pattern
        return pattern

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def promote(self, pattern_id: str, to: str, promoted_at: str) -> ImmunityPattern:
        """Move *pattern_id* to lifecycle stage *to*, if the step is legal."""
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            raise LifecycleError(f"No immunity pattern {pattern_id!r}.")
        if to not in _TRANSITIONS.get(pattern.lifecycle, set()):
            raise LifecycleError(
                f"Cannot move {pattern_id!r} from {pattern.lifecycle!r} to {to!r}. "
                f"Allowed from {pattern.lifecycle!r}: "
                f"{', '.join(sorted(_TRANSITIONS.get(pattern.lifecycle, set()))) or 'nothing'}."
            )
        pattern.lifecycle = to  # type: ignore[assignment]
        pattern.promoted_at = promoted_at
        return pattern

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get(self, pattern_id: str) -> ImmunityPattern | None:
        return self._patterns.get(pattern_id)

    def all_patterns(self) -> list[ImmunityPattern]:
        return sorted(self._patterns.values(), key=lambda p: p.id)

    def clear(self) -> None:
        """Drop every pattern. Used when a replay session restarts."""
        self._patterns.clear()
