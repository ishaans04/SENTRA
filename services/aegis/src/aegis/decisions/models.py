"""The decision model (PRD §11.4): approvals, their bases and conditions, and evidence.

From the AEGIS design: a decision is a node that stands on other nodes, and
when what it stands on fails, everything built on it is found by walking
forward. Here the decision is an operator's approval of agent work, its bases
are typed conditions, and its epoch is the fencing token every run carries.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from aegis.conditions.predicates import Predicate, Result

DecisionStatus = Literal[
    "proposed", "active", "needs_review", "suspended", "withdrawn", "discarded"
]
EvidenceKind = Literal["observed", "checked", "stated", "interpreted", "background"]


class Basis(BaseModel):
    """One reason the decision may stand. Every condition in it must hold."""

    id: str
    conditions: list[str] = Field(default_factory=list)
    accepted: bool = True


class Condition(BaseModel):
    id: str
    predicate: Predicate
    #: The condition in the operator's terms, used in read-backs and alerts.
    plain: str
    last_result: Result | None = None
    witnesses: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    id: str
    statement: str
    #: Short name for what is approved ("Reporting"), used in alerts.
    subject: str
    #: The actor whose runs this decision authorises.
    actor: str
    dictated_text: str = ""
    bases: list[Basis] = Field(default_factory=list)
    status: DecisionStatus = "proposed"
    epoch: int = 1
    #: Pre-authorised: hold this decision's queued sends if it is suspended.
    hold_rule: bool = True
    provenance: list[str] = Field(default_factory=list)

    @property
    def live(self) -> bool:
        return self.status in {"active", "needs_review"}


class Evidence(BaseModel):
    id: str
    kind: EvidenceKind
    source: str
    context: dict[str, Any] = Field(default_factory=dict)
    applies: bool | None = None
    cites: list[str] = Field(default_factory=list)


class ConditionProposal(BaseModel):
    predicate: Predicate
    plain: str


class DecisionProposal(BaseModel):
    """What interpretation produces from a dictated approval, before ids exist."""

    statement: str
    subject: str
    actor: str
    conditions: list[ConditionProposal] = Field(default_factory=list)
    hold_rule: bool = True
