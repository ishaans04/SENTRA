"""Validation, redaction, and provenance checks for incoming observations.

Ingest is a trust boundary. Everything downstream — the ledger, the graph, every
finding — assumes an event is well-formed and carries no payload content. This
module is the only place that assumption is established.

Redaction happens here rather than at display time so that sensitive content is
never written to the ledger in the first place. HIVE reasons about the *shape*
of interactions; it has no need to hold what was said.
"""

from __future__ import annotations

from typing import Any, get_args

from pydantic import ValidationError

from hive_core.domain.models import Action, ObservationEvent

#: Actions the platform understands, derived from the domain type so the two
#: can never drift apart.
VALID_ACTIONS: frozenset[str] = frozenset(get_args(Action))

#: Context keys whose values may carry payload content or credentials. Matched
#: as substrings, case-insensitively.
_REDACTED_KEY_HINTS = (
    "content",
    "prompt",
    "body",
    "payload",
    "message",
    "secret",
    "password",
    "token",
    "credential",
    "api_key",
    "apikey",
)

#: Keys that survive redaction despite matching a hint above, because they hold
#: a derived label rather than the content itself.
_REDACTION_ALLOWLIST = frozenset({"content_fingerprint"})

REDACTED = "[redacted at ingest]"


class EventValidationError(ValueError):
    """Raised when a raw observation cannot be accepted."""


class EventValidator:
    """Turn an untrusted dictionary into a typed, redacted observation."""

    @staticmethod
    def validate(raw: dict[str, Any]) -> ObservationEvent:
        """Validate and redact *raw*, returning a typed event.

        Raises
        ------
        EventValidationError
            If the event is missing required identity fields, names an unknown
            action, or fails type validation.
        """
        if not isinstance(raw, dict):
            raise EventValidationError("An observation must be a JSON object.")

        action = raw.get("action")
        if action not in VALID_ACTIONS:
            raise EventValidationError(
                f"Unknown action {action!r}. Expected one of: {', '.join(sorted(VALID_ACTIONS))}."
            )

        for field in ("event_id", "actor", "target"):
            if not raw.get(field):
                raise EventValidationError(f"An observation must carry a non-empty {field!r}.")

        if not isinstance(raw.get("sequence"), int):
            raise EventValidationError("An observation must carry an integer 'sequence'.")

        candidate = dict(raw)
        candidate["context"] = EventValidator.redact(raw.get("context") or {})

        try:
            return ObservationEvent(**candidate)
        except ValidationError as exc:
            raise EventValidationError(str(exc)) from exc

    @staticmethod
    def redact(context: dict[str, Any]) -> dict[str, Any]:
        """Replace any context value that could carry payload content."""
        redacted: dict[str, Any] = {}
        for key, value in context.items():
            lowered = key.lower()
            if lowered in _REDACTION_ALLOWLIST:
                redacted[key] = value
            elif any(hint in lowered for hint in _REDACTED_KEY_HINTS):
                redacted[key] = REDACTED
            else:
                redacted[key] = value
        return redacted
