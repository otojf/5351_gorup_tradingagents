"""Deterministic risk engine (FR-A1).

``evaluate_risk`` is a pure function: same inputs and policy yield the same
verdicts and rule outcomes (only the timestamp and measured latency vary). It has
no network, file I/O, LLM, or LangGraph dependency.

Rules (v1, ordinary cash-funded long BUY; affected-sector concentration):

- R1 stop-loss required for an actionable long BUY.
- R2 projected single-name weight <= single_name_cap.
- R3 projected affected-sector exposure <= sector_cap.
- R4 reward-to-risk >= min_reward_risk with stop < entry < target.
- R5 ticker not blacklisted.
- R6 input integrity: inputs present, finite, consistent, direction unambiguous.

A genuine BUY must increase the position and be affordable from cash. Each rule
is PASS, VIOLATED, NOT_APPLICABLE, or UNKNOWN. UNKNOWN (insufficient input) is
not VIOLATED. Aggregation precedence is REJECTED > NEEDS_REVIEW > APPROVED, and
every applicable rule is evaluated (no first-fail short circuit).
"""

from __future__ import annotations

import hashlib
import math
import time
from datetime import UTC, datetime

from .models import (
    DecisionStatus,
    RiskEvaluation,
    RiskInputs,
    RiskVerdict,
    RuleOutcome,
    RuleResult,
)
from .policy import RiskPolicy
from .portfolio_snapshot import (
    SnapshotError,
    current_stock_value,
    normalize_sector,
    projected_sector_exposure,
    sector_conflict,
    target_sector,
    validate_snapshot,
)
from .sizing import projected_stock_value, weight_problem

R0 = "R0_ALL_RULES_PASSED"
R1 = "R1_STOP_LOSS_REQUIRED"
R2 = "R2_SINGLE_NAME_CAP"
R3 = "R3_SECTOR_CONCENTRATION"
R4 = "R4_REWARD_RISK"
R5 = "R5_BLACKLIST"
R6 = "R6_INPUT_INTEGRITY"

# Directions the model may express; anything else is ambiguous.
_LONG = {"Buy", "Overweight"}
_SHORT = {"Sell", "Underweight"}
_HOLD = {"Hold"}
_ACTIONABLE = _LONG | _SHORT


def _is_finite(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _classify(term: str | None) -> str | None:
    """Bucket a single action/rating term into long/short/hold, or ``None``."""
    if term in _LONG:
        return "long"
    if term in _SHORT:
        return "short"
    if term in _HOLD:
        return "hold"
    return None


def _direction(action: str | None, rating: str | None) -> tuple[str | None, bool, bool]:
    """Resolve the decision direction, consistency, and final-rating validity.

    Returns ``(direction, consistent, rating_valid)`` where ``direction`` is
    ``"long"``, ``"short"``, ``"hold"``, or ``None`` (unusable). ``consistent`` is
    ``False`` when the action and the model rating point in opposite directions.
    ``rating_valid`` is ``True`` only when the *final PortfolioDecision rating* is a
    recognized term; a missing, unrecognized, or ``REVIEW`` rating is not valid and
    must never be replaced by the Trader's action to obtain approval (BUG-001).
    """
    a_bucket = _classify(action)
    r_bucket = _classify(rating)
    rating_valid = r_bucket is not None

    if a_bucket and r_bucket and a_bucket != r_bucket:
        return None, False, rating_valid
    direction = a_bucket or r_bucket
    return direction, True, rating_valid


def _rule(rule_id: str, outcome: RuleOutcome, detail: str = "",
          observed: float | None = None, threshold: float | None = None) -> RuleResult:
    return RuleResult(rule_id=rule_id, outcome=outcome, detail=detail,
                      observed=observed, threshold=threshold)


def _evaluate_integrity(inputs: RiskInputs, direction, consistent: bool,
                        rating_valid: bool) -> RuleResult:
    """R6: inputs present, finite, consistent, direction unambiguous, affordable.

    Records UNKNOWN for: a missing/unrecognized/``REVIEW`` final rating (BUG-001),
    contradictory direction, ambiguous direction, non-finite prices, an
    unusable/inconsistent/stale portfolio snapshot, and a purchase the cash cannot
    fund. R6 does not duplicate the cap (R2) or sector (R3) checks.
    """
    if not consistent:
        return _rule(R6, RuleOutcome.UNKNOWN, "action and model_rating disagree on direction")
    if not rating_valid:
        # The final PortfolioDecision rating must be usable; it is never replaced by
        # the Trader's action to obtain an approval.
        return _rule(R6, RuleOutcome.UNKNOWN,
                     "final model rating is missing, unrecognized, or REVIEW")
    if direction is None:
        return _rule(R6, RuleOutcome.UNKNOWN, "direction is ambiguous")
    if direction == "short":
        # v1 supports ordinary cash-funded long BUY only. A short/SELL cannot be
        # approved pending team confirmation of risk-reducing criteria.
        return _rule(R6, RuleOutcome.UNKNOWN,
                     "short/SELL is unsupported in v1 (pending team confirmation)")
    for name, value in (("entry_price", inputs.entry_price),
                        ("stop_loss", inputs.stop_loss),
                        ("price_target", inputs.price_target)):
        if value is not None and not _is_finite(value):
            return _rule(R6, RuleOutcome.UNKNOWN, f"{name} is not finite")

    portfolio = inputs.portfolio
    if portfolio is not None:
        try:
            validate_snapshot(portfolio, inputs.trade_date)
        except SnapshotError as exc:
            return _rule(R6, RuleOutcome.UNKNOWN, f"portfolio snapshot unusable: {exc}")

        # Affordability of a cash-funded increase, when the buy size is known.
        tp = inputs.target_position
        if tp is not None and weight_problem(tp.target_position_weight) is None:
            weight = tp.target_position_weight
            current = current_stock_value(portfolio, inputs.ticker)
            projected = projected_stock_value(weight, portfolio.portfolio_value)
            increase = projected - current
            if increase > portfolio.cash + 1e-9:
                return _rule(R6, RuleOutcome.UNKNOWN,
                             "purchase is not affordable from available cash",
                             observed=increase, threshold=portfolio.cash)
    return _rule(R6, RuleOutcome.PASS, "inputs are present and consistent")


def _evaluate_stop_loss(inputs: RiskInputs, direction) -> RuleResult:
    """R1: a long actionable BUY must carry a stop-loss. HOLD/SHORT are N/A here."""
    if direction != "long":
        return _rule(R1, RuleOutcome.NOT_APPLICABLE, "stop-loss required only for long BUY")
    if inputs.stop_loss is None:
        return _rule(R1, RuleOutcome.VIOLATED, "stop-loss is missing for a long BUY")
    if not _is_finite(inputs.stop_loss):
        return _rule(R1, RuleOutcome.UNKNOWN, "stop-loss is not finite")
    return _rule(R1, RuleOutcome.PASS, "stop-loss present", observed=inputs.stop_loss)


def _evaluate_single_name(inputs: RiskInputs, direction, policy: RiskPolicy) -> RuleResult:
    """R2: projected single-name weight <= cap, and the BUY must increase the position.

    UNKNOWN only when the weight is missing/unusable, or when a usable snapshot
    shows the buy does not genuinely increase the holding. Affordability and
    snapshot consistency are R6's job.
    """
    if direction != "long":
        return _rule(R2, RuleOutcome.NOT_APPLICABLE, "single-name cap applies to long BUY")
    if inputs.target_position is None:
        return _rule(R2, RuleOutcome.UNKNOWN, "target_position is missing")
    weight = inputs.target_position.target_position_weight
    problem = weight_problem(weight)
    if problem is not None:
        return _rule(R2, RuleOutcome.UNKNOWN, problem)
    if weight > policy.single_name_cap:
        return _rule(R2, RuleOutcome.VIOLATED,
                     "projected single-name weight exceeds the cap",
                     observed=weight, threshold=policy.single_name_cap)
    # A genuine BUY must increase the existing position (when the book is usable).
    if inputs.portfolio is not None:
        try:
            validate_snapshot(inputs.portfolio, inputs.trade_date)
        except SnapshotError:
            # Snapshot integrity is R6's concern; the cap itself already passed.
            return _rule(R2, RuleOutcome.PASS, "projected weight within cap",
                         observed=weight, threshold=policy.single_name_cap)
        current = current_stock_value(inputs.portfolio, inputs.ticker)
        projected = projected_stock_value(weight, inputs.portfolio.portfolio_value)
        if projected - current <= 0.0:
            return _rule(R2, RuleOutcome.UNKNOWN,
                         "BUY does not increase the existing position (not a genuine buy)",
                         observed=projected - current)
    return _rule(R2, RuleOutcome.PASS, "projected weight within cap",
                 observed=weight, threshold=policy.single_name_cap)


def _evaluate_sector(inputs: RiskInputs, direction, policy: RiskPolicy) -> RuleResult:
    """R3: projected affected-sector exposure <= cap.

    Sector names are normalized (whitespace-stripped, case-folded) for both the
    target and every holding, so equivalent spellings aggregate identically
    (BUG-002). UNKNOWN when the target position/portfolio is missing, the weight or
    snapshot is unusable, any holding lacks a sector, the target sector is unknown,
    or the explicit target sector contradicts an already-held ticker's
    classification (a conflict must not re-scope the calculation into a false PASS).
    """
    if direction != "long":
        return _rule(R3, RuleOutcome.NOT_APPLICABLE, "sector cap applies to long BUY")
    if inputs.target_position is None or inputs.portfolio is None:
        return _rule(R3, RuleOutcome.UNKNOWN, "target_position or portfolio snapshot is missing")
    weight = inputs.target_position.target_position_weight
    if weight_problem(weight) is not None:
        return _rule(R3, RuleOutcome.UNKNOWN, "target weight is unusable")
    try:
        validate_snapshot(inputs.portfolio, inputs.trade_date)
    except SnapshotError as exc:
        return _rule(R3, RuleOutcome.UNKNOWN, f"portfolio snapshot unusable: {exc}")
    # An unclassified holding makes the book's sector exposure unknowable.
    if any(normalize_sector(h.sector) is None for h in inputs.portfolio.holdings):
        return _rule(R3, RuleOutcome.UNKNOWN, "a holding has no sector classification")
    # A conflicting explicit target sector must not hide the real concentration.
    if sector_conflict(inputs.portfolio, inputs.ticker, inputs.target_position.sector):
        return _rule(R3, RuleOutcome.UNKNOWN,
                     "explicit target sector conflicts with the held classification")
    sector = target_sector(inputs.portfolio, inputs.ticker, inputs.target_position.sector)
    if sector is None:
        return _rule(R3, RuleOutcome.UNKNOWN, "target sector is unknown")
    projected_value = projected_sector_exposure(inputs.portfolio, inputs.ticker, sector, weight)
    if not _is_finite(projected_value):
        return _rule(R3, RuleOutcome.UNKNOWN, "projected sector exposure is not finite")
    exposure = projected_value / inputs.portfolio.portfolio_value
    if exposure > policy.sector_cap + 1e-12:
        return _rule(R3, RuleOutcome.VIOLATED,
                     "projected sector exposure exceeds the cap",
                     observed=exposure, threshold=policy.sector_cap)
    return _rule(R3, RuleOutcome.PASS, "projected sector exposure within cap",
                 observed=exposure, threshold=policy.sector_cap)


def _evaluate_reward_risk(inputs: RiskInputs, direction) -> RuleResult:
    """R4: reward-to-risk >= min and stop < entry < target (direction-aware)."""
    if direction == "hold":
        return _rule(R4, RuleOutcome.NOT_APPLICABLE, "reward-to-risk applies to a trade, not HOLD")
    if direction is None:
        return _rule(R4, RuleOutcome.UNKNOWN, "direction is ambiguous")
    if inputs.entry_price is None or inputs.stop_loss is None or inputs.price_target is None:
        return _rule(R4, RuleOutcome.UNKNOWN, "entry, stop, or target is missing")
    if not _is_finite(inputs.entry_price) or not _is_finite(inputs.stop_loss) \
            or not _is_finite(inputs.price_target):
        return _rule(R4, RuleOutcome.UNKNOWN, "a price field is not finite")
    entry, stop, target = inputs.entry_price, inputs.stop_loss, inputs.price_target
    if direction == "long":
        # For an ordinary long stock BUY, provided prices must be strictly positive.
        # Non-positive levels cannot be real prices and must never be approved
        # (BUG-003), even when their ordering/ratio would otherwise look valid.
        if entry <= 0.0 or stop <= 0.0 or target <= 0.0:
            return _rule(R4, RuleOutcome.VIOLATED,
                         "long BUY prices must be strictly positive")
        if not (stop < entry < target):
            return _rule(R4, RuleOutcome.VIOLATED,
                         "long ordering must be stop < entry < target")
        risk = entry - stop
        reward = target - entry
    else:  # short (risk-reducing direction), pending team confirmation
        if entry <= 0.0 or stop <= 0.0 or target <= 0.0:
            return _rule(R4, RuleOutcome.VIOLATED,
                         "short BUY prices must be strictly positive")
        if not (stop > entry > target):
            return _rule(R4, RuleOutcome.VIOLATED,
                         "short ordering must be target < entry < stop")
        risk = stop - entry
        reward = entry - target
    if risk <= 0.0:
        return _rule(R4, RuleOutcome.VIOLATED, "risk per unit is not positive")
    # Threshold comes from the policy applied by the caller; default is used here.
    ratio = reward / risk
    return _rule(R4, RuleOutcome.PASS, "reward-to-risk computable", observed=ratio)


def _apply_reward_threshold(rule: RuleResult, policy: RiskPolicy) -> RuleResult:
    """Turn R4's PASS into VIOLATED when the computed ratio is below the floor."""
    if rule.outcome != RuleOutcome.PASS or rule.observed is None:
        return rule
    if rule.observed + 1e-12 < policy.min_reward_risk:
        return RuleResult(rule_id=rule.rule_id, outcome=RuleOutcome.VIOLATED,
                          detail="reward-to-risk is below the floor",
                          observed=rule.observed, threshold=policy.min_reward_risk)
    return RuleResult(rule_id=rule.rule_id, outcome=RuleOutcome.PASS,
                      detail=rule.detail, observed=rule.observed,
                      threshold=policy.min_reward_risk)


def _evaluate_blacklist(inputs: RiskInputs, policy: RiskPolicy) -> RuleResult:
    """R5: the analyzed ticker must not be blacklisted."""
    if policy.is_blacklisted(inputs.ticker):
        return _rule(R5, RuleOutcome.VIOLATED, "ticker is on the blacklist")
    return _rule(R5, RuleOutcome.PASS, "ticker is not blacklisted")


def _snapshot(inputs: RiskInputs) -> dict:
    """A minimal, redacted input snapshot for the audit record."""
    tp = inputs.target_position
    pf = inputs.portfolio
    return {
        "ticker": inputs.ticker,
        "trade_date": inputs.trade_date,
        "action": inputs.action,
        "model_rating": inputs.model_rating,
        "entry_price": inputs.entry_price,
        "stop_loss": inputs.stop_loss,
        "price_target": inputs.price_target,
        "target_position_weight": tp.target_position_weight if tp else None,
        "target_sector": tp.sector if tp else None,
        "portfolio_value": pf.portfolio_value if pf else None,
        "cash": pf.cash if pf else None,
        "holdings_count": len(pf.holdings) if pf else 0,
        "valuation_date": pf.valuation_date if pf else None,
    }


def _decide(rule_results: list[RuleResult], direction) -> tuple[RiskVerdict, DecisionStatus]:
    """Aggregate per-rule outcomes into a verdict and delivery status."""
    outcomes = {r.rule_id: r.outcome for r in rule_results}
    violated = any(o == RuleOutcome.VIOLATED for o in outcomes.values())
    unknown = any(o == RuleOutcome.UNKNOWN for o in outcomes.values())

    if violated:
        verdict = RiskVerdict.REJECTED
    elif unknown:
        verdict = RiskVerdict.NEEDS_REVIEW
    else:
        verdict = RiskVerdict.APPROVED

    if verdict == RiskVerdict.REJECTED:
        status = DecisionStatus.BLOCKED
    elif verdict == RiskVerdict.NEEDS_REVIEW:
        status = DecisionStatus.PENDING_REVIEW
    elif direction == "hold":
        status = DecisionStatus.NO_TRADE
    else:
        status = DecisionStatus.ACTIONABLE
    return verdict, status


def _direction_is_enforceable(direction, consistent: bool) -> bool:
    """Whether an actionable (long/short) trade is well-defined enough to be actionable."""
    return consistent and direction in ("long", "short")


def evaluate_risk(inputs: RiskInputs, policy: RiskPolicy | None = None) -> RiskEvaluation:
    """Evaluate one decision against the policy; return a complete, audited result."""
    policy = policy or RiskPolicy()
    started_wall = datetime.now(UTC)
    started = time.perf_counter()
    direction, consistent, rating_valid = _direction(inputs.action, inputs.model_rating)

    rule_results: list[RuleResult] = []
    rule_results.append(_evaluate_stop_loss(inputs, direction))
    rule_results.append(_evaluate_single_name(inputs, direction, policy))
    rule_results.append(_evaluate_sector(inputs, direction, policy))
    rule_results.append(_apply_reward_threshold(_evaluate_reward_risk(inputs, direction), policy))
    rule_results.append(_evaluate_blacklist(inputs, policy))
    rule_results.append(_evaluate_integrity(inputs, direction, consistent, rating_valid))

    # A positive marker when every rule passes, so every verdict carries an id.
    all_pass = all(r.outcome in (RuleOutcome.PASS, RuleOutcome.NOT_APPLICABLE)
                   for r in rule_results)
    if all_pass:
        rule_results.append(_rule(R0, RuleOutcome.PASS, "all applicable rules passed"))

    verdict, status = _decide(rule_results, direction)

    # Safety: an approved but not-enforceable direction (ambiguous/inconsistent,
    # unsupported SELL) must never be ACTIONABLE. R6 already makes these UNKNOWN ->
    # NEEDS_REVIEW; this is a defensive second guard.
    if verdict == RiskVerdict.APPROVED and direction in ("long", "short") \
            and not _direction_is_enforceable(direction, consistent):
        verdict, status = RiskVerdict.NEEDS_REVIEW, DecisionStatus.PENDING_REVIEW

    evaluated_rule_ids = [r.rule_id for r in rule_results]
    triggered = [r.rule_id for r in rule_results if r.outcome == RuleOutcome.VIOLATED]

    latency_ms = (time.perf_counter() - started) * 1000.0

    return RiskEvaluation(
        verdict=verdict,
        decision_status=status,
        model_rating=inputs.model_rating,
        evaluated_rule_ids=evaluated_rule_ids,
        triggered_violation_ids=triggered,
        rule_results=rule_results,
        policy_version=policy.version,
        policy_hash=policy.policy_hash,
        input_snapshot=_snapshot(inputs),
        evaluated_at_utc=started_wall.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        latency_ms=latency_ms,
    )


def audit_id_for(evaluation: RiskEvaluation) -> str:
    """A deterministic audit id from the evaluation's content and result."""
    basis = (
        evaluation.policy_hash
        + "|" + evaluation.evaluated_at_utc
        + "|" + str(evaluation.verdict)
        + "|" + evaluation.input_snapshot.get("ticker", "")
        + "|" + evaluation.input_snapshot.get("trade_date", "")
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
