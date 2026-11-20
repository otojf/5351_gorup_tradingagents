"""Stage 2 integration adapter: the single authoritative risk evaluation point.

The Portfolio Manager output boundary is where both structured decisions exist and
after which every consumer (propagate signal, state log, memory rating, reports,
CLI) reads ``final_rating``. This adapter:

- converts the two structured decisions plus a caller-supplied ``risk_portfolio``
  into :class:`RiskInputs` (never parsing Markdown, never inventing values);
- invokes :func:`tradingagents.risk_gate.evaluate_risk` **exactly once**;
- persists the durable audit via :func:`persist_audit` **before** the caller
  publishes an actionable ``final_rating``;
- preserves the model rating in ``model_rating`` and returns the *effective*
  public rating (``REVIEW`` unless APPROVED).

The adapter has no network, file-I/O on the evaluation path, or LLM dependency.
Only :func:`persist_audit` writes to disk, and only when given an ``audit_dir``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from tradingagents.agents.rating import RATING_REVIEW
from tradingagents.dataflows.symbols import safe_ticker_component

from . import evaluate_risk
from .models import PortfolioRiskSnapshot, RiskEvaluation, RiskInputs, TargetPosition
from .sizing import parse_position_sizing

logger = logging.getLogger(__name__)


class AuditPersistenceError(RuntimeError):
    """Raised when an actionable recommendation cannot be durably audited.

    Fail-closed: no actionable recommendation may be published without a successful
    durable audit write.
    """


def _configured_risk_inputs(risk_portfolio):
    """Validate the caller's config mapping; unusable parts become None."""
    if not risk_portfolio:
        return None, None
    if not isinstance(risk_portfolio, Mapping):
        logger.warning("risk_portfolio is not a mapping; failing closed")
        return None, None
    try:
        tp = risk_portfolio.get("target_position")
        target_position = TargetPosition.model_validate(tp) if tp is not None else None
        snap = risk_portfolio.get("snapshot")
        portfolio = PortfolioRiskSnapshot.model_validate(snap) if snap is not None else None
    except (ValidationError, TypeError, AttributeError) as exc:
        logger.warning("risk_portfolio is unusable (%s); failing closed", exc)
        return None, None
    return target_position, portfolio


def _effective_target_position(trader_proposal, configured):
    """Combine the caller's target with the Trader's declared sizing.

    Parsed text can only tighten the caller's number. An unparseable non-empty
    sizing, or sizing without a caller target, is unusable (R2 UNKNOWN) and must
    never become an approval on its own.
    """
    sizing = (
        getattr(trader_proposal, "position_sizing", None)
        if trader_proposal is not None
        else None
    )
    if sizing is None:
        return configured
    if not isinstance(sizing, str):
        return None
    if not sizing.strip():
        return configured
    parsed = parse_position_sizing(sizing)
    if parsed is None:
        return None
    if configured is None or configured.target_position_weight is None:
        return None
    weight = max(configured.target_position_weight, parsed)
    return TargetPosition(
        target_position_weight=weight,
        sector=configured.sector,
    )


def _build_inputs_core(ticker, trade_date, trader_proposal, portfolio_decision, risk_portfolio):
    """Convert structured decisions + caller portfolio data into ``RiskInputs``.

    Missing structured objects become ``None`` fields (the engine then records
    R6 UNKNOWN). ``risk_portfolio`` is the additive Python-API config
    ``{"snapshot": {...}, "target_position": {...}}``; absent parts stay ``None``
    so the gate fails closed.
    """
    action = None
    if trader_proposal is not None:
        action = getattr(getattr(trader_proposal, "action", None), "value", None)
        entry_price = getattr(trader_proposal, "entry_price", None)
        stop_loss = getattr(trader_proposal, "stop_loss", None)
    else:
        entry_price = stop_loss = None

    price_target = None
    model_rating = None
    if portfolio_decision is not None:
        price_target = getattr(portfolio_decision, "price_target", None)
        model_rating = getattr(getattr(portfolio_decision, "rating", None), "value", None)

    target_position, portfolio = _configured_risk_inputs(risk_portfolio)
    target_position = _effective_target_position(trader_proposal, target_position)

    return RiskInputs(
        ticker=ticker,
        trade_date=str(trade_date),
        action=action,
        entry_price=entry_price,
        stop_loss=stop_loss,
        price_target=price_target,
        model_rating=model_rating,
        target_position=target_position,
        portfolio=portfolio,
    )


def build_inputs(ticker, trade_date, trader_proposal, portfolio_decision, risk_portfolio=None):
    """Public: convert structured inputs into ``RiskInputs`` without evaluating."""
    return _build_inputs_core(ticker, trade_date, trader_proposal, portfolio_decision, risk_portfolio)


def _effective_rating(evaluation: RiskEvaluation) -> str:
    """The effective public rating: the model rating when APPROVED, including an
    approved HOLD whose decision status is NO_TRADE; otherwise the REVIEW sentinel."""
    if evaluation.verdict == "APPROVED":
        return evaluation.model_rating or RATING_REVIEW
    return RATING_REVIEW


def apply_gate(ticker, trade_date, trader_proposal, portfolio_decision, risk_portfolio=None,
               *, policy=None, audit_dir=None):
    """Evaluate once, persist the durable audit, and return the state updates.

    Returns a dict with ``model_rating``, ``final_rating`` (effective),
    ``risk_verdict``, ``decision_status`` and ``risk_evaluation`` (the
    :class:`RiskEvaluation`). The durable audit is written before an actionable
    rating is returned; if persistence raises, this function propagates the
    failure so no actionable rating is published.
    """
    inputs = _build_inputs_core(ticker, trade_date, trader_proposal, portfolio_decision,
                                risk_portfolio)
    evaluation = evaluate_risk(inputs, policy)

    # Durable audit must be established before an actionable rating can be published.
    # A missing destination must not silently count as successful persistence: an
    # otherwise-APPROVED decision is downgraded to a non-actionable result instead of
    # being published as ACTIONABLE without a durable audit.
    actionable = str(evaluation.verdict) == "APPROVED" and \
        str(evaluation.decision_status) == "ACTIONABLE"
    if actionable and audit_dir is None:
        return {
            "model_rating": evaluation.model_rating,
            "final_rating": RATING_REVIEW,
            "risk_verdict": "NEEDS_REVIEW",
            "decision_status": "PENDING_REVIEW",
            "risk_evaluation": evaluation,
        }
    persist_audit(evaluation, audit_dir)

    return {
        "model_rating": evaluation.model_rating,
        "final_rating": _effective_rating(evaluation),
        "risk_verdict": str(evaluation.verdict),
        "decision_status": str(evaluation.decision_status),
        "risk_evaluation": evaluation,
    }


def _audit_payload(evaluation: RiskEvaluation) -> dict:
    """The serialisable audit record persisted to disk and the state log."""
    return {
        "verdict": str(evaluation.verdict),
        "decision_status": str(evaluation.decision_status),
        "model_rating": evaluation.model_rating,
        "policy_version": evaluation.policy_version,
        "policy_hash": evaluation.policy_hash,
        "evaluated_at_utc": evaluation.evaluated_at_utc,
        "latency_ms": evaluation.latency_ms,
        "evaluated_rule_ids": list(evaluation.evaluated_rule_ids),
        "triggered_violation_ids": list(evaluation.triggered_violation_ids),
        "input_snapshot": dict(evaluation.input_snapshot),
        "rule_results": [
            {
                "rule_id": r.rule_id,
                "outcome": str(r.outcome),
                "detail": r.detail,
                "observed": r.observed,
                "threshold": r.threshold,
            }
            for r in evaluation.rule_results
        ],
    }


def audit_payload(evaluation: RiskEvaluation) -> dict:
    """Public serializer for the audit record (used by the eval manifest)."""
    return _audit_payload(evaluation)


def persist_audit(evaluation: RiskEvaluation, audit_dir=None):
    """Durable audit writer. Writes one JSON record per evaluation when a directory
    is given; otherwise returns the payload without touching disk (used for the
    in-memory benchmark). Returns the serialisable payload.

    This is the real function the production integration calls for every
    evaluation, and the one the durable-audit-failure test patches.
    """
    payload = _audit_payload(evaluation)
    if audit_dir is not None:
        try:
            directory = Path(audit_dir)
            directory.mkdir(parents=True, exist_ok=True)
            ticker = safe_ticker_component(
                str(evaluation.input_snapshot.get("ticker", "unknown"))
            )
            stamp = evaluation.evaluated_at_utc.replace(":", "").replace(".", "").replace("-", "")
            path = directory / f"risk_audit_{ticker}_{stamp}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
        except OSError as exc:
            raise AuditPersistenceError(
                f"could not persist risk audit to {audit_dir}: {exc}"
            ) from exc
    return payload
