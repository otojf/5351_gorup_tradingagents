"""Five individually isolated violations for FR-A1's 5/5 acceptance criterion.

Each fixture violates exactly one rule; the expected verdict and that rule's
VIOLATED outcome are asserted, and it is asserted that no *other* rule is
VIOLATED (unrelated inputs stay valid). UNKNOWN is not a violation.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import (
    R1,
    R2,
    R3,
    R4,
    R5,
    evaluate,
    make_buy,
    make_target,
    outcomes,
    violated_ids,
)

# Cash-funded book used only by the sector violation: MSFT 350,000 technology,
# AAPL unheld, cash 650,000, Financials fill to 1,000,000. Projected AAPL 50,000
# -> Technology 400,000 = 40% > 30%, while every other rule stays in bounds.
_SECTOR_OVER_BOOK = {
    "valuation_date": "2026-01-09",
    "portfolio_value": 1_000_000.0,
    "cash": 600_000.0,
    "holdings": [
        {"ticker": "AAPL", "market_value": 0.0, "sector": "Technology"},
        {"ticker": "MSFT", "market_value": 350_000.0, "sector": "Technology"},
        {"ticker": "JPM", "market_value": 50_000.0, "sector": "Financials"},
    ],
}


@pytest.mark.unit
def test_missing_stop_loss_isolated():
    """FR-A1 violation 1: missing stop-loss -> REJECTED, only R1 VIOLATED.

    R4 may be UNKNOWN here (reward-to-risk cannot be computed without a stop);
    UNKNOWN is not a violation, so it is not counted among the violated rules.
    """
    result = evaluate(make_buy(stop_loss=None))
    assert result.verdict == "REJECTED"
    assert violated_ids(result) == {R1}
    assert outcomes(result)[R1] == "VIOLATED"


@pytest.mark.unit
def test_single_name_over_ten_percent_isolated():
    """FR-A1 violation 2: single-name > 10% -> REJECTED, only R2 VIOLATED."""
    result = evaluate(make_buy(target_position=make_target(0.12)))
    assert result.verdict == "REJECTED"
    assert violated_ids(result) == {R2}


@pytest.mark.unit
def test_sector_over_thirty_percent_isolated():
    """FR-A1 violation 3: projected sector concentration > 30% -> only R3 VIOLATED."""
    result = evaluate(make_buy(portfolio=_SECTOR_OVER_BOOK))
    assert result.verdict == "REJECTED"
    assert violated_ids(result) == {R3}


@pytest.mark.unit
def test_reward_risk_below_floor_isolated():
    """FR-A1 violation 4: reward-to-risk < 1.5 -> only R4 VIOLATED."""
    result = evaluate(make_buy(stop_loss=90.0, price_target=105.0))
    assert result.verdict == "REJECTED"
    assert violated_ids(result) == {R4}


@pytest.mark.unit
def test_blacklisted_isolated():
    """FR-A1 violation 5: blacklisted -> only R5 VIOLATED."""
    rg = __import__("tradingagents.risk_gate", fromlist=["RiskPolicy"])
    result = evaluate(make_buy(), policy=rg.RiskPolicy(blacklist=frozenset({"AAPL"})))
    assert result.verdict == "REJECTED"
    assert violated_ids(result) == {R5}


@pytest.mark.unit
def test_all_rules_pass_is_approved():
    """Control: the baseline valid BUY passes every rule."""
    result = evaluate(make_buy())
    assert result.verdict == "APPROVED"
    assert violated_ids(result) == set()
    assert outcomes(result)
