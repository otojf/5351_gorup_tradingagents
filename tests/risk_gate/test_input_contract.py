"""Malformed, missing, contradictory, and inconsistent inputs (FR-A1, INV-A1, R6).

Absence of evidence is never approval: anything the gate cannot fully evaluate
resolves to NEEDS_REVIEW with the relevant rule UNKNOWN (not VIOLATED), and the
decision status is non-actionable. Validation errors must never yield an
actionable recommendation.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import (
    R2,
    R3,
    R4,
    R6,
    evaluate,
    make_buy,
    make_portfolio,
    make_target,
    outcomes,
    unknown_ids,
)


@pytest.mark.unit
def test_missing_target_position_weight_needs_review():
    """FR-A1: a BUY with no structured weight cannot be approved (R2 UNKNOWN)."""
    result = evaluate(make_buy(target_position=None))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"
    assert R2 in unknown_ids(result)
    assert outcomes(result)[R2] == "UNKNOWN"


@pytest.mark.unit
def test_missing_portfolio_snapshot_needs_review():
    """FR-A1: sector exposure cannot be proven without a snapshot (R3 UNKNOWN)."""
    result = evaluate(make_buy(portfolio=None))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"
    assert R3 in unknown_ids(result)


@pytest.mark.unit
def test_unknown_sector_needs_review():
    """FR-A1: an unclassified holding prevents approval (R3 UNKNOWN)."""
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 20_000.0, "sector": None},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
        cash=830_000.0,
        portfolio_value=1_000_000.0,
    )
    result = evaluate(make_buy(portfolio=portfolio))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"
    assert R3 in unknown_ids(result)


@pytest.mark.unit
def test_missing_reward_leg_needs_review():
    """FR-A1: a missing target leaves the ratio unprovable (R4 UNKNOWN)."""
    result = evaluate(make_buy(price_target=None))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"
    assert R4 in unknown_ids(result)


@pytest.mark.unit
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_prices_need_review(bad):
    """FR-A1: NaN/inf price fields cannot be approved and are not actionable."""
    result = evaluate(make_buy(entry_price=bad))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"


@pytest.mark.unit
def test_contradictory_directions_need_review():
    """FR-A1: proposal action and decision rating in opposite directions is ambiguous."""
    result = evaluate(make_buy(action="Buy", model_rating="Sell"))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"
    assert R6 in unknown_ids(result)


@pytest.mark.unit
def test_inconsistent_valuation_date_prevents_approval():
    """FR-A1: a stale/ inconsistent valuation date is inconsistent portfolio data."""
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
        cash=830_000.0,
        portfolio_value=1_000_000.0,
        valuation_date="2020-01-01",
    )
    result = evaluate(make_buy(portfolio=portfolio))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status == "PENDING_REVIEW"


@pytest.mark.unit
def test_inconsistent_holdings_do_not_sum_to_value_needs_review():
    """FR-A1: holdings+cash not equal to portfolio_value is inconsistent (R6 UNKNOWN)."""
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
        cash=100_000.0,               # 20k+150k+100k = 270k != 1,000,000
        portfolio_value=1_000_000.0,
    )
    result = evaluate(make_buy(portfolio=portfolio))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status != "ACTIONABLE"


@pytest.mark.unit
def test_affordability_failure_needs_review():
    """FR-A1: an affordable-looking increase the book cannot fund is NEEDS_REVIEW.

    Consistent book with total 1,000,000:
        cash 10,000 + AAPL 20,000 + MSFT 150,000 + others 820,000 = 1,000,000.
    Target AAPL weight 0.05 -> projected 50,000, a genuine +30,000 increase, but
    only 10,000 cash is free. R2 passes (0.05 <= 0.10) and R3 passes (projected
    Technology = 200,000 = 20% <= 30%), so affordability is the only blocker.
    """
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
            {"ticker": "JPM", "market_value": 300_000.0, "sector": "Financials"},
            {"ticker": "XOM", "market_value": 300_000.0, "sector": "Energy"},
            {"ticker": "PG", "market_value": 220_000.0, "sector": "Consumer Staples"},
        ],
        cash=10_000.0,
        portfolio_value=1_000_000.0,
    )
    result = evaluate(make_buy(target_position=make_target(0.05), portfolio=portfolio))
    assert result.verdict == "NEEDS_REVIEW"
    assert result.decision_status != "ACTIONABLE"
