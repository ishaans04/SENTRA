"""Ingest is a trust boundary: everything downstream assumes it held."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_core.ingest.validator import REDACTED, EventValidationError, EventValidator


def _raw(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "event_id": "e1",
        "sequence": 1,
        "occurred_at": "2026-09-19T10:00:00Z",
        "actor": "Support Agent",
        "action": "read",
        "target": "Fictional CRM",
        "context": {},
        "provenance": {"adapter": "test"},
        "result": "success",
    }
    base.update(overrides)
    return base


class TestAcceptance:
    def test_a_well_formed_event_is_accepted(self) -> None:
        event = EventValidator.validate(_raw())
        assert event.event_id == "e1"
        assert event.action == "read"

    @pytest.mark.parametrize(
        "action",
        ["read", "write", "call", "message", "delegate", "discover", "send", "execute", "block"],
    )
    def test_every_declared_action_is_accepted(self, action: str) -> None:
        assert EventValidator.validate(_raw(action=action)).action == action


class TestRejection:
    def test_unknown_action_is_rejected_by_name(self) -> None:
        with pytest.raises(EventValidationError, match="Unknown action"):
            EventValidator.validate(_raw(action="exfiltrate"))

    @pytest.mark.parametrize("field", ["event_id", "actor", "target"])
    def test_missing_identity_field_is_rejected(self, field: str) -> None:
        with pytest.raises(EventValidationError, match=field):
            EventValidator.validate(_raw(**{field: ""}))

    def test_non_integer_sequence_is_rejected(self) -> None:
        with pytest.raises(EventValidationError, match="sequence"):
            EventValidator.validate(_raw(sequence="third"))

    def test_a_non_object_is_rejected(self) -> None:
        with pytest.raises(EventValidationError):
            EventValidator.validate("not an event")  # type: ignore[arg-type]


class TestRedaction:
    """HIVE reasons about interaction shape and has no need to hold content."""

    @pytest.mark.parametrize(
        "key",
        [
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
            "apiKey",
            "user_prompt",
            "response_body",
        ],
    )
    def test_content_bearing_keys_are_redacted(self, key: str) -> None:
        event = EventValidator.validate(_raw(context={key: "sensitive value"}))
        assert event.context[key] == REDACTED

    def test_a_derived_fingerprint_survives(self) -> None:
        event = EventValidator.validate(
            _raw(context={"content_fingerprint": "ticket-derived-summary"})
        )
        assert event.context["content_fingerprint"] == "ticket-derived-summary"

    def test_structural_context_survives(self) -> None:
        event = EventValidator.validate(
            _raw(context={"workflow": "ticket-resolution", "phase": "baseline"})
        )
        assert event.context["workflow"] == "ticket-resolution"
        assert event.context["phase"] == "baseline"

    def test_redaction_does_not_mutate_the_caller_dictionary(self) -> None:
        raw = _raw(context={"prompt": "original"})
        EventValidator.validate(raw)
        assert raw["context"] == {"prompt": "original"}


class TestFixtureHygiene:
    """Every shipped fixture must survive the same boundary as live input."""

    def test_all_scenario_fixtures_load_cleanly(self) -> None:
        from hive_core.lab.scenarios import ScenarioLoader
        from tests.conftest import SCENARIOS

        loader = ScenarioLoader(SCENARIOS)
        descriptors = loader.available()
        assert descriptors, "no scenario fixtures found"
        for descriptor in descriptors:
            events = loader.load(descriptor.id)
            assert len(events) == descriptor.event_count

    def test_a_fixture_with_repeated_ids_is_refused(self, tmp_path: Path) -> None:
        from hive_core.lab.scenarios import ScenarioError, ScenarioLoader

        line = (
            '{"event_id": "dup", "sequence": %d, "occurred_at": "2026-09-19T10:00:00Z", '
            '"actor": "A", "action": "read", "target": "S", "context": {}, '
            '"provenance": {}, "result": "success"}'
        )
        (tmp_path / "broken.jsonl").write_text(f"{line % 1}\n{line % 2}\n", encoding="utf-8")

        with pytest.raises(ScenarioError, match="repeats event ids"):
            ScenarioLoader(tmp_path).load("broken")
