"""Recovery interpretation: grammar, recorded responses and the model chain."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aegis.interpret.chain import Interpreter
from aegis.recovery.plan import (
    ApplyControl,
    CancelRun,
    Preserve,
    Rebuild,
    RevokeAccess,
)
from aegis.scenario import Session

STORY = (
    "Stop this reporting run, remove its scratchpad access, and rebuild the report from "
    "approved summaries. Keep the support work."
)
EXPECTED = [
    CancelRun(run_id="R-1"),
    ApplyControl(control_id="deny-reporting-scratchpad-read"),
    RevokeAccess(actor="reporting-agent", resource="scratchpad"),
    Rebuild(decision_id="D-1", sources=["report_store/approved_summaries"]),
    Preserve(scope="support-agent"),
]


@pytest.fixture
async def session(fixtures_dir: Path) -> Session:
    s = Session("s-interp", fixtures_dir)
    await s.run_to(8)
    return s


async def test_grammar_parses_storyline_recovery(session: Session) -> None:
    assert session.grammar.parse_recovery(STORY, session) == EXPECTED


@pytest.mark.parametrize(
    "text",
    [
        "Okay so stop this reporting run, remove its scratchpad access and rebuild the report "
        "from approved summaries. Keep the support work.",
        "um, cancel the reporting run. revoke its scratchpad access. rebuild the report from "
        "the approved summaries. keep the support work",
    ],
)
async def test_recovery_with_filler_words(session: Session, text: str) -> None:
    assert session.grammar.parse_recovery(text, session) == EXPECTED


async def test_unknown_clause_is_not_guessed(session: Session) -> None:
    assert (
        session.grammar.parse_recovery("Stop this reporting run and email the CEO.", session)
        is None
    )


def _raises(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    raise RuntimeError("rate limited")


def _invalid(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    args: dict[str, Any] = {"steps": [{"kind": "CANCEL_RUN", "run_id": "R-9"}]}
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


def _valid(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    args = {"steps": [step.model_dump() for step in EXPECTED]}
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


async def test_fallback_order(session: Session) -> None:
    interpreter = Interpreter(
        session,
        mode="chain",
        models=[("gemini", FunctionModel(_raises)), ("groq", FunctionModel(_invalid))],
    )
    steps, used = await interpreter.recovery(STORY)
    assert used == "grammar"
    assert steps == EXPECTED
    assert interpreter.last_failures == [
        "gemini: gemini call failed: rate limited",
        "groq: groq proposed a plan that does not validate: There is no run R-9.",
    ]
    results = [e for e in session.ledger.events() if e.kind == "interpretation.result"]
    assert results[-1].payload["provider"] == "grammar"


async def test_valid_model_output_is_used_and_recorded(session: Session, tmp_path: Path) -> None:
    interpreter = Interpreter(
        session,
        mode="chain",
        models=[("gemini", FunctionModel(_valid))],
        recordings=tmp_path / "recorded.json",
    )
    steps, used = await interpreter.recovery("Contain the reporting problem please.")
    assert (steps, used) == (EXPECTED, "gemini")

    replay = Interpreter(session, mode="off", recordings=tmp_path / "recorded.json")
    again, used_again = await replay.recovery("contain the reporting problem please")
    assert (again, used_again) == (EXPECTED, "recorded")


async def test_model_off_never_calls_a_model(session: Session) -> None:
    interpreter = Interpreter(session, mode="off", models=[("gemini", FunctionModel(_raises))])
    steps, used = await interpreter.recovery(STORY)
    assert (steps, used) == (EXPECTED, "grammar")
    assert interpreter.last_failures == []
    assert not [e for e in session.ledger.events() if e.kind.startswith("interpretation.")]


async def test_approval_through_the_chain(session: Session) -> None:
    proposal, used = await Interpreter(session, mode="grammar").approval(
        "Approve reporting if it only reads from approved summaries"
    )
    assert used == "grammar"
    assert proposal.actor == "reporting-agent"


async def test_uninterpretable_text_says_so(session: Session) -> None:
    with pytest.raises(ValueError, match="could not"):
        await Interpreter(session, mode="off").recovery("make it all better")
