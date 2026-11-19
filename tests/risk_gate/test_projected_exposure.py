"""Projected post-trade exposure calculations (FR-A1 §5.3).

Under the documented cash-funded long assumption:

    projected_stock_value  = target_weight * portfolio_value
    projected_sector_value = current_sector_value - current_stock_value
                             + projected_stock_value

Exposure uses market values, never average cost. The target stock's sector is
supplied explicitly on ``target_position`` when the stock is not already held;
it is never inferred from prose or fetched over the network. These tests pin the
arithmetic used by R2/R3.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import (
    R3,
    evaluate,
    make_buy,
    make_portfolio,
    make_target,
    violated_ids,
)


@pytest.mark.unit
def test_sector_exposure_sums_holdings_in_same_sector():
    """FR-A1 §5.3: same-sector holdings aggregate before the 30% test."""
    # current Technology = 300,000 (AAPL 100k + MSFT 100k + NVDA 100k); target is
    # AAPL at 0.05 * 1M = 50,000, i.e. a *decrease* — use a book where it's an
    # increase to keep the fixture a genuine BUY. Instead buy a new tech name.
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "MSFT", "market_value": 100_000.0, "sector": "Technology"},
            {"ticker": "NVDA", "market_value": 100_000.0, "sector": "Technology"},
            {"ticker": "JPM", "market_value": 100_000.0, "sector": "Financials"},
        ],
        cash=700_000.0,
        portfolio_value=1_000_000.0,
    )
    # AAPL unheld; projected Technology = 200,000 + 50,000 = 250,000 = 25% <= 30%.
    result = evaluate(make_buy(portfolio=portfolio, target_position=make_target(0.05)))
    assert result.verdict == "APPROVED"


@pytest.mark.unit
def test_sector_exposure_uses_market_value_not_cost():
    """FR-A1 §5.3: exposure uses market values, pushing Technology over 30%."""
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 0.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 300_000.0, "sector": "Technology"},
            {"ticker": "JPM", "market_value": 640_000.0, "sector": "Financials"},
        ],
        cash=60_000.0,
        portfolio_value=1_000_000.0,
    )
    # projected Technology = 300,000 + 50,000 = 350,000 = 35% > 30%.
    result = evaluate(make_buy(portfolio=portfolio))
    assert result.verdict == "REJECTED"
    assert R3 in violated_ids(result)


@pytest.mark.unit
def test_increase_that_crosses_sector_limit_is_rejected():
    """FR-A1 §5.3: a purchase that crosses 30% is rejected even if under before."""
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 0.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 280_000.0, "sector": "Technology"},
            {"ticker": "JPM", "market_value": 660_000.0, "sector": "Financials"},
        ],
        cash=60_000.0,
        portfolio_value=1_000_000.0,
    )
    # current Technology 280,000 (28%) <= 30%, but projected 280,000 + 50,000
    # = 330,000 = 33% > 30%.
    result = evaluate(make_buy(portfolio=portfolio))
    assert result.verdict == "REJECTED"
    assert R3 in violated_ids(result)


@pytest.mark.unit
def test_weight_denominator_is_portfolio_value():
    """FR-A1 §5.3: single-name weight is against total portfolio value."""
    result = evaluate(make_buy(target_position=make_target(0.10)))
    assert result.verdict == "APPROVED"


@pytest.mark.unit
def test_buy_that_reduces_position_is_not_approved():
    """FR-A1 §5.4: a BUY that does not increase the existing position is not approved."""
    # Holds AAPL 100,000; target weight 0.05 of 1,000,000 = 50,000 < 100,000.
    portfolio = make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 100_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
        cash=750_000.0,
        portfolio_value=1_000_000.0,
    )
    result = evaluate(make_buy(portfolio=portfolio, target_position=make_target(0.05)))
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"
