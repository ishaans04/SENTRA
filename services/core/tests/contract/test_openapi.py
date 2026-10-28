"""The committed contract must describe the service that actually runs.

A hand-maintained OpenAPI file drifts. Here the document is generated from the
application and checked in, and this test fails the build when the two disagree —
so the contract in the repository is the contract judges and clients get.

Run ``uv run python -m hive_core.contract`` to regenerate it after a route change.
"""

from __future__ import annotations

import json
from pathlib import Path

from hive_core.contract import CONTRACT_PATH, build_document
from hive_core.main import app

EXAMPLES = Path(CONTRACT_PATH).resolve().parents[1] / "examples"


class TestCommittedSpec:
    def test_the_committed_document_is_current(self) -> None:
        committed = json.loads(Path(CONTRACT_PATH).read_text(encoding="utf-8"))
        assert committed == build_document(), (
            "contracts/openapi/hive-core-v1.json is stale. Regenerate it with "
            "`uv run python -m hive_core.contract`."
        )

    def test_every_route_is_described(self) -> None:
        document = build_document()
        live = {
            str(getattr(route, "path", ""))
            for route in app.routes
            if getattr(route, "include_in_schema", False) and hasattr(route, "methods")
        }
        assert live <= set(document["paths"]), "a route exists that the contract omits"

    def test_the_document_declares_the_local_server(self) -> None:
        document = build_document()
        assert any("127.0.0.1" in server["url"] for server in document["servers"])


class TestExamples:
    """The shipped examples must genuinely pass and fail validation."""

    def test_the_valid_example_is_accepted(self) -> None:
        from hive_core.ingest.validator import EventValidator

        raw = json.loads((EXAMPLES / "valid_observation_event.json").read_text(encoding="utf-8"))
        event = EventValidator.validate(raw)
        assert event.event_id == raw["event_id"]

    def test_the_invalid_example_is_rejected(self) -> None:
        import pytest

        from hive_core.ingest.validator import EventValidationError, EventValidator

        raw = json.loads((EXAMPLES / "invalid_observation_event.json").read_text(encoding="utf-8"))
        with pytest.raises(EventValidationError):
            EventValidator.validate(raw)
