"""The three pieces lifted from AEGIS: clock, failover chain, recorded responses."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.clock import LogicalClock
from aegis.interpret.providers import FailoverChain, ProviderError
from aegis.interpret.recorded import RecordedResponses


class TestLogicalClock:
    def test_ticks_are_deterministic_and_monotonic(self) -> None:
        a, b = LogicalClock("2026-10-28T10:00:00Z"), LogicalClock("2026-10-28T10:00:00Z")
        first = [a.tick() for _ in range(3)]
        assert first == [b.tick() for _ in range(3)]
        assert first == ["2026-10-28T10:00:01Z", "2026-10-28T10:00:02Z", "2026-10-28T10:00:03Z"]

    def test_now_does_not_advance(self) -> None:
        clock = LogicalClock("2026-10-28T10:00:00Z")
        assert clock.now() == clock.now() == "2026-10-28T10:00:00Z"

    def test_observe_never_rewinds(self) -> None:
        clock = LogicalClock("2026-10-28T10:00:00Z")
        clock.observe("2026-10-28T10:05:00Z")
        clock.observe("2026-10-28T10:01:00Z")
        assert clock.now() == "2026-10-28T10:05:00Z"


class _Fails:
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, text: str) -> str:
        raise ProviderError(f"{self.name} is down")


class _Echo:
    name = "echo"

    async def run(self, text: str) -> str:
        return text.upper()


class TestFailoverChain:
    async def test_first_provider_that_answers_wins(self) -> None:
        chain: FailoverChain[str] = FailoverChain([_Fails("gemini"), _Echo()])
        assert await chain.run("hi") == "HI"
        assert chain.last_used == "echo"
        assert chain.failures == ["gemini: gemini is down"]

    async def test_all_failing_raises_with_every_reason(self) -> None:
        chain: FailoverChain[str] = FailoverChain([_Fails("gemini"), _Fails("groq")])
        with pytest.raises(ProviderError, match="gemini is down .* groq is down"):
            await chain.run("hi")

    def test_empty_chain_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            FailoverChain([])


class TestRecordedResponses:
    def test_round_trip_through_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "recorded.json"
        rec = RecordedResponses(path)
        rec.put("recovery", "Stop this run.", {"steps": []})
        rec.save()
        again = RecordedResponses(path)
        assert again.get("recovery", "Stop this run.") == {"steps": []}
        assert len(again) == 1

    def test_key_ignores_case_and_spacing(self, tmp_path: Path) -> None:
        rec = RecordedResponses(tmp_path / "r.json")
        rec.put("approval", "Approve  reporting.", {"ok": True})
        assert rec.get("approval", "approve reporting.") == {"ok": True}
        assert rec.get("recovery", "approve reporting.") is None

    def test_missing_file_starts_empty(self, tmp_path: Path) -> None:
        assert len(RecordedResponses(tmp_path / "absent.json")) == 0
