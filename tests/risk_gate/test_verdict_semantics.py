"""Verdict semantics: precedence, completeness, and actionability (FR-A1, §5.2).

The model rating, the risk verdict, and the deliverable status are independent.
Aggregation precedence is REJECTED > NEEDS_REVIEW > APPROVED, all applicable
rules are collected, and an approved HOLD is NO_TRADE, never ACTIONABLE.

UNKNOWN (insufficient input) is distinct from VIOLATED (a rule broken).
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import (
    R0,
    R4,
    evaluate,
    make_buy,
    outcomes,
    unknown_ids,
    violated_ids,
)


@pytest.mark.unit
def test_approved_buy_is_actionable():
    """FR-A1 §5.2: APPROVED + trade -> ACTIONABLE."""
    result = evaluate(make_buy())
    assert result.verdict == "APPROVED"
    assert result.decision_status == "ACTIONABLE"


@pytest.mark.unit
def test_rejected_is_blocked():
    """FR-A1 §5.2: REJECTED -> BLOCKED."""
    result = evaluate(make_buy(stop_loss=None))
    assert result.verdict == "REJECTED"
    assert result.decision_status == "BLOCKED"


@pytest.mark.unit
def test_needs_review_is_pending_review():
    """FR-A1 §5.2: NEEDS_REVIEW -> PENDING_REVIEW."""
    result = evaluate(make_buy(price_target=None))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"


@pytest.mark.unit
def test_precedence_rejected_over_needs_review():
    """FR-A1 §5.2: REJECTED dominates NEEDS_REVIEW when both apply.

    Missing weight (R2 UNKNOWN) and missing stop (R1 VIOLATED) both present;
    the verdict must be REJECTED.
    """
    result = evaluate(make_buy(stop_loss=None, target_position=None))
    assert result.verdict == "REJECTED"


@pytest.mark.unit
def test_unknown_is_not_violated():
    """FR-A1 §5.2: a rule with insufficient input is UNKNOWN, not VIOLATED."""
    result = evaluate(make_buy(price_target=None))
    assert R4 in unknown_ids(result)
    assert R4 not in violated_ids(result)
    assert outcomes(result)[R4] == "UNKNOWN"


@pytest.mark.unit
def test_all_applicable_rules_are_collected():
    """FR-A1 §5.2: no first-fail short circuit; triggered ids are a subset."""
    result = evaluate(make_buy(stop_loss=105.0, price_target=95.0))
    assert R4 in violated_ids(result)
    assert result.evaluated_rule_ids
    assert set(result.triggered_violation_ids) <= set(result.evaluated_rule_ids)


@pytest.mark.unit
def test_clean_run_carries_rule_ids():
    """FR-A1: 100% of verdicts carry rule IDs, including successes (R0)."""
    result = evaluate(make_buy())
    assert result.rule_results
    assert R0 in {r.rule_id for r in result.rule_results}
    assert result.evaluated_rule_ids


@pytest.mark.unit
def test_model_rating_preserved_on_reject():
    """FR-A1 §5.1: the model's rating is preserved even when the gate rejects."""
    result = evaluate(make_buy(model_rating="Buy", stop_loss=None))
    assert result.verdict == "REJECTED"
    assert result.model_rating == "Buy"


@pytest.mark.unit
def test_approved_hold_is_no_trade():
    """FR-A1 §5.2: an approved HOLD is NO_TRADE, never ACTIONABLE."""
    data = make_buy(action="Hold", model_rating="Hold",
                    entry_price=None, stop_loss=None, price_target=None,
                    target_position=None, portfolio=None)
    result = evaluate(data)
    assert result.decision_status != "ACTIONABLE"
    if result.verdict == "APPROVED":
        assert result.decision_status == "NO_TRADE"
