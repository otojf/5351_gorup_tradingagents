"""Per-rule behavior for the deterministic risk gate (FR-A1, INV-A1).

Each test names the requirement/invariant it enforces. The engine is imported at
test execution time via ``require_engine`` so the tests fail (RED) while the gate
is absent, rather than skipping.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import (
    R0,
    R1,
    R2,
    R3,
    R4,
    R5,
    evaluate,
    make_buy,
    make_target,
    violated_ids,
)


@pytest.mark.unit
def test_valid_buy_is_approved_with_a_rule_id():
    """FR-A1: a fully in-bounds, consistent long BUY is APPROVED and carries R0."""
    result = evaluate(make_buy())
    assert result.verdict == "APPROVED"
    assert result.decision_status == "ACTIONABLE"
    assert R0 in {r.rule_id for r in result.rule_results}


@pytest.mark.unit
def test_r1_missing_stop_loss_rejects_a_buy():
    """FR-A1/INV-A1: a BUY without a stop-loss is not APPROVED (R1 VIOLATED)."""
    result = evaluate(make_buy(stop_loss=None))
    assert result.verdict == "REJECTED"
    assert R1 in violated_ids(result)


@pytest.mark.unit
def test_r2_single_name_over_cap_rejects():
    """FR-A1: projected single-name weight above 10% is rejected (R2 VIOLATED)."""
    result = evaluate(make_buy(target_position=make_target(0.12)))
    assert result.verdict == "REJECTED"
    assert R2 in violated_ids(result)


@pytest.mark.unit
def test_r3_sector_over_cap_rejects():
    """FR-A1: a purchase that pushes projected sector exposure above 30% (R3 VIOLATED).

    Current Technology = MSFT 350,000 (AAPL 0). Target AAPL weight 0.05 of a
    1,000,000 book = 50,000 projected; Technology 350,000 + 50,000 = 400,000 = 40%.
    """
    portfolio = {
        "valuation_date": "2026-01-09",
        "portfolio_value": 1_000_000.0,
        "cash": 650_000.0,
        "holdings": [
            {"ticker": "AAPL", "market_value": 0.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 350_000.0, "sector": "Technology"},
        ],
    }
    result = evaluate(make_buy(portfolio=portfolio))
    assert result.verdict == "REJECTED"
    assert R3 in violated_ids(result)


@pytest.mark.unit
def test_r4_low_reward_risk_rejects():
    """FR-A1: a reward-to-risk ratio below 1.5 rejects (R4 VIOLATED)."""
    # entry 100, stop 90 (risk 10), target 105 (reward 5) -> RR 0.5
    result = evaluate(make_buy(stop_loss=90.0, price_target=105.0))
    assert result.verdict == "REJECTED"
    assert R4 in violated_ids(result)


@pytest.mark.unit
def test_r5_blacklisted_ticker_rejects():
    """FR-A1: a blacklisted ticker is rejected (R5 VIOLATED)."""
    rg = __import__("tradingagents.risk_gate", fromlist=["RiskPolicy"])
    result = evaluate(make_buy(), policy=rg.RiskPolicy(blacklist=frozenset({"AAPL"})))
    assert result.verdict == "REJECTED"
    assert R5 in violated_ids(result)
