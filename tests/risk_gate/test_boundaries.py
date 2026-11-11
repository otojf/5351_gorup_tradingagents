"""Exact threshold boundaries for the risk gate (FR-A1).

Thresholds are the draft 10% / 30% / 1.5. Boundary values on the allowed side
must PASS; values just beyond must be rejected. Sector tests verify **projected
post-trade** exposure under the documented cash-funded assumption, not merely the
current holdings.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import (
    R2,
    R3,
    R4,
    evaluate,
    make_buy,
    make_target,
    violated_ids,
)

# A fixed book for sector tests: portfolio 1,000,000, MSFT 150,000 technology,
# and a non-technology holding filling the rest. The target stock is AAPL,
# currently unheld, so projected Technology = MSFT + projected AAPL value.
_BOOK_BASE = 1_000_000.0


def _sector_book(projected_tech_total):
    """Build a cash-funded book where, after buying AAPL at weight 0.05
    (50,000), Technology equals ``projected_tech_total``.

    AAPL is unheld (0); MSFT carries the rest of Technology. Cash funds the
    AAPL purchase (>= 50,000) and Financials fill the remainder, so the book
    sums to portfolio_value and the purchase is affordable.
    """
    aapl_projected = 0.05 * _BOOK_BASE  # 50,000
    msft = projected_tech_total - aapl_projected
    cash = 60_000.0  # enough to fund the 50,000 purchase
    financials = _BOOK_BASE - (msft + cash)
    return {
        "valuation_date": "2026-01-09",
        "portfolio_value": _BOOK_BASE,
        "cash": cash,
        "holdings": [
            {"ticker": "AAPL", "market_value": 0.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": msft, "sector": "Technology"},
            {"ticker": "JPM", "market_value": financials, "sector": "Financials"},
        ],
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "weight, approved",
    [
        # VALID_BUY holds AAPL 20,000, so a target weight whose projected value
        # does not increase the position is not a genuine BUY and is not approved.
        (0.0, False),          # projected 0 < held 20,000 -> reduces, not approved
        (0.02, False),         # projected 20,000 == held 20,000 -> no increase
        (0.021, True),         # projected 21,000 > 20,000 -> genuine increase
        (0.099, True),
        (0.10, True),          # cap is inclusive
        (0.1000001, False),    # over the cap
        (0.11, False),
    ],
    ids=["zero_reduces", "no_increase", "just_increase", "below", "exactly_10pct",
         "just_over", "over"],
)
def test_single_name_cap_boundary(weight, approved):
    """FR-A1: single-name cap is inclusive at 10% and a BUY must increase the holding."""
    result = evaluate(make_buy(target_position=make_target(weight)))
    assert (result.verdict == "APPROVED") is approved
    if not approved and weight > 0.10:
        assert R2 in violated_ids(result)


@pytest.mark.unit
@pytest.mark.parametrize(
    "projected_tech_total, approved",
    [
        (250_000.0, True),    # 25%
        (299_999.0, True),    # just below
        (300_000.0, True),    # exactly 30% (inclusive)
        (300_001.0, False),   # just over
        (350_000.0, False),   # 35%
    ],
    ids=["below", "just_below", "exactly_30pct", "just_over", "over"],
)
def test_sector_cap_boundary(projected_tech_total, approved):
    """FR-A1: sector cap is inclusive at 30% on projected post-trade exposure."""
    data = make_buy(portfolio=_sector_book(projected_tech_total))
    result = evaluate(data)
    assert (result.verdict == "APPROVED") is approved
    if not approved:
        assert R3 in violated_ids(result)


@pytest.mark.unit
@pytest.mark.parametrize(
    "target, approved",
    [
        (115.0, True),      # RR 1.5 exactly (reward 15 / risk 10)
        (114.9999, False),  # just below
        (130.0, True),      # comfortably above
    ],
    ids=["exactly_1_5", "just_below", "above"],
)
def test_reward_risk_boundary(target, approved):
    """FR-A1: reward-to-risk floor is inclusive at 1.5."""
    result = evaluate(make_buy(stop_loss=90.0, price_target=target))
    assert (result.verdict == "APPROVED") is approved
    if not approved:
        assert R4 in violated_ids(result)
