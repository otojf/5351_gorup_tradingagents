"""Pydantic models for the FR-A1 deterministic risk gate.

The engine's contract: structured inputs (``RiskInputs`` and its parts), structured
outputs (``RuleResult``, ``RiskEvaluation``, ``RiskAuditRecord``), and the enums
that keep the model rating, the risk verdict, and the delivery status distinct.

This module is pure data: no network, file I/O, LLM, or LangGraph import. Validation
is strict about finiteness (``allow_inf_nan=False``) so a malformed numeric cannot
sneak through as a usable value; the values that matter to the rules are also
checked for finiteness at evaluation time and degrade to ``UNKNOWN`` when unusable.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RiskVerdict(StrEnum):
    """The gate's independent judgment about a decision."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DecisionStatus(StrEnum):
    """What the rest of the system may do with the decision."""

    ACTIONABLE = "ACTIONABLE"
    BLOCKED = "BLOCKED"
    PENDING_REVIEW = "PENDING_REVIEW"
    NO_TRADE = "NO_TRADE"


class RuleOutcome(StrEnum):
    """Per-rule result. ``UNKNOWN`` (insufficient input) is not ``VIOLATED``."""

    PASS = "PASS"
    VIOLATED = "VIOLATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class RuleResult(BaseModel):
    """One rule's outcome, with the numbers that produced it (audit)."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    outcome: RuleOutcome
    detail: str = ""
    observed: float | None = None
    threshold: float | None = None


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class TargetPosition(BaseModel):
    """The projected post-trade single-name exposure.

    ``target_position_weight`` is the projected weight of the analyzed instrument
    as a fraction of total portfolio value. ``sector`` names the instrument's
    sector and is required when the instrument is not already held. Values are not
    coerced; a non-finite or out-of-range weight is treated as unusable (UNKNOWN),
    never as an approval.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    target_position_weight: float | None = None
    sector: str | None = None


class Holding(BaseModel):
    """A current portfolio holding, by current market value (never average cost)."""

    model_config = ConfigDict(allow_inf_nan=False)

    ticker: str
    market_value: float
    sector: str | None = None


class PortfolioRiskSnapshot(BaseModel):
    """A minimal, internally consistent snapshot of the caller's book.

    Cash-funded long assumption (v1): the trade is paid from ``cash``.
    Consistency: ``cash + sum(holdings.market_value) == portfolio_value`` within a
    small tolerance; an inconsistent snapshot is not usable for exposure rules.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    valuation_date: str
    portfolio_value: float
    cash: float
    holdings: list[Holding] = Field(default_factory=list)


class RiskInputs(BaseModel):
    """Everything the gate evaluates, assembled by the caller from structured data.

    The analyzed ticker, the decision fields, and the caller's book. ``action`` and
    ``model_rating`` are the model's own outputs; a contradiction between them is
    ambiguous and cannot be approved.

    Numeric decision fields allow ``inf``/``nan`` at the model layer so a malformed
    value is representable; the engine then records it as UNKNOWN (NEEDS_REVIEW)
    rather than letting it validate into an usable number. It must never become an
    approval.
    """

    model_config = ConfigDict(allow_inf_nan=True)

    ticker: str
    trade_date: str
    action: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    price_target: float | None = None
    model_rating: str | None = None
    target_position: TargetPosition | None = None
    portfolio: PortfolioRiskSnapshot | None = None


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class RiskEvaluation(BaseModel):
    """The gate's complete, auditable result for one decision."""

    model_config = ConfigDict(frozen=True)

    verdict: RiskVerdict
    decision_status: DecisionStatus
    model_rating: str | None
    evaluated_rule_ids: list[str] = Field(default_factory=list)
    triggered_violation_ids: list[str] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
    policy_version: str
    policy_hash: str
    input_snapshot: dict
    evaluated_at_utc: str
    latency_ms: float


class RiskAuditRecord(BaseModel):
    """An audit envelope around one evaluation."""

    model_config = ConfigDict(frozen=True)

    audit_id: str
    evaluation: RiskEvaluation
