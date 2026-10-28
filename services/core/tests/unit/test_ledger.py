"""The ledger is the evidence, so its guarantees are worth stating explicitly."""

from __future__ import annotations

from hive_core.ledger.repository import LedgerRepository
from tests.conftest import observation


def _ledger(count: int = 3) -> LedgerRepository:
    ledger = LedgerRepository()
    ledger.extend([observation(f"e{i}", i, "Agent", "read", "Store") for i in range(1, count + 1)])
    return ledger


class TestAppendOnly:
    def test_duplicate_event_id_is_rejected(self) -> None:
        ledger = LedgerRepository()
        assert ledger.append(observation("e1", 1, "A", "read", "S")) is True
        assert ledger.append(observation("e1", 9, "B", "write", "T")) is False
        assert ledger.total == 1

    def test_events_are_held_in_sequence_order_regardless_of_arrival(self) -> None:
        ledger = LedgerRepository()
        ledger.append(observation("e3", 3, "A", "read", "S"))
        ledger.append(observation("e1", 1, "A", "read", "S"))
        ledger.append(observation("e2", 2, "A", "read", "S"))
        assert [e.sequence for e in ledger.all_events()] == [1, 2, 3]

    def test_extend_reports_how_many_were_new(self) -> None:
        ledger = _ledger(3)
        again = [observation(f"e{i}", i, "Agent", "read", "Store") for i in range(1, 5)]
        assert ledger.extend(again) == 1


class TestCursor:
    def test_cursor_starts_before_the_first_event(self) -> None:
        assert _ledger().cursor == 0
        assert _ledger().replayed() == []

    def test_step_advances_one_event_and_returns_it(self) -> None:
        ledger = _ledger()
        stepped = ledger.advance()
        assert [e.event_id for e in stepped] == ["e1"]
        assert ledger.cursor == 1

    def test_advance_to_returns_everything_passed_over(self) -> None:
        ledger = _ledger(5)
        stepped = ledger.advance(3)
        assert [e.event_id for e in stepped] == ["e1", "e2", "e3"]
        assert ledger.cursor == 3

    def test_advancing_past_the_end_is_a_no_op(self) -> None:
        ledger = _ledger(2)
        ledger.advance(99)
        assert ledger.advance() == []
        assert ledger.cursor == 2

    def test_rewind_moves_the_cursor_without_touching_the_record(self) -> None:
        ledger = _ledger(3)
        ledger.advance(3)
        ledger.rewind()
        assert ledger.cursor == 0
        assert ledger.total == 3, "rewinding replay position must not erase evidence"
        assert ledger.replayed() == []

    def test_pending_and_replayed_partition_the_log(self) -> None:
        ledger = _ledger(5)
        ledger.advance(2)
        assert len(ledger.replayed()) == 2
        assert len(ledger.pending()) == 3


class TestIntegrityChecks:
    def test_duplicate_ids_are_reported_for_the_caller_to_reject(self) -> None:
        events = [
            observation("a", 1, "A", "read", "S"),
            observation("b", 2, "A", "read", "S"),
            observation("a", 3, "A", "read", "S"),
        ]
        assert LedgerRepository.duplicate_event_ids(events) == ["a"]

    def test_clean_input_reports_nothing(self) -> None:
        events = [observation(f"e{i}", i, "A", "read", "S") for i in range(1, 4)]
        assert LedgerRepository.duplicate_event_ids(events) == []
