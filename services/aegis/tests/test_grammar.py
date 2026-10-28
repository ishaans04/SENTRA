"""The deterministic grammar: dictated approvals to typed proposals, with no model."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis.conditions.predicates import ReadsOnlyFrom
from aegis.interpret.grammar import Grammar
from aegis.interpret.readback import read_back_decision

STORY = (
    "Approve reporting, on the condition that the Reporting Agent only reads from "
    "the approved, sanitized report store."
)


@pytest.fixture
def grammar(fixtures_dir: Path) -> Grammar:
    return Grammar.load(fixtures_dir)


def test_storyline_approval_parses(grammar: Grammar) -> None:
    proposal = grammar.parse_approval(STORY)
    assert proposal is not None
    assert (proposal.statement, proposal.subject, proposal.actor) == (
        "Reporting may proceed",
        "Reporting",
        "reporting-agent",
    )
    [condition] = proposal.conditions
    assert condition.predicate == ReadsOnlyFrom(
        actor="reporting-agent", resources=["report_store/approved_summaries"]
    )
    assert condition.plain == "this agent receives only sanitized summaries"


@pytest.mark.parametrize(
    "text",
    [
        "Okay, so, approve reporting on the condition that the reporting agent only reads "
        "from the approved sanitized report store.",
        "um approve reporting as long as it only reads from approved summaries",
        "APPROVE REPORTING, PROVIDED THAT THE REPORTING AGENT ONLY READS FROM THE APPROVED "
        "SUMMARIES!",
        "Please approve reporting if this agent only reads from the sanitized summaries.",
    ],
)
def test_flow_filler_words_parse(grammar: Grammar, text: str) -> None:
    proposal = grammar.parse_approval(text)
    assert proposal is not None
    assert proposal.conditions[0].predicate == ReadsOnlyFrom(
        actor="reporting-agent", resources=["report_store/approved_summaries"]
    )


def test_unknown_resource_rejected(grammar: Grammar) -> None:
    assert grammar.parse_approval("Approve reporting if it only reads from the moon") is None


def test_unrelated_text_is_not_an_approval(grammar: Grammar) -> None:
    assert grammar.parse_approval("What is the weather like?") is None


def test_condition_about_another_agent_is_rejected(grammar: Grammar) -> None:
    text = "Approve reporting if the support agent only reads from approved summaries"
    assert grammar.parse_approval(text) is None


def test_readback_names_the_condition_and_the_hold_rule(grammar: Grammar) -> None:
    proposal = grammar.parse_approval(STORY)
    assert proposal is not None
    text = read_back_decision(proposal, grammar.labels)
    assert text.splitlines() == [
        "I will record this approval: Reporting may proceed.",
        "Condition: Reporting Agent only reads from Approved summaries.",
        "Checked as: ReadsOnlyFrom(reporting-agent, [report_store/approved_summaries]).",
        "If the condition fails, I will hold this approval's queued sends.",
        "Interpreted by: grammar (no model call)",
    ]
