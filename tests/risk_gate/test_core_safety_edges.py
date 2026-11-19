"""FR-A1 core safety edges: regression tests for three potential defects.

These probe areas not covered by the main suite, using the existing builders:

1. An invalid final model rating (e.g. ``REVIEW``, missing, unrecognized) must
   never let a valid Trader BUY become APPROVED/ACTIONABLE. The Trader's action
   must not substitute for an invalid final PortfolioDecision.
2. An inconsistent target-sector classification must not let a decision that
   pushes the affected sector over the cap be approved, and harmless case/
   whitespace variations in sector names must not bypass R3.
3. A long stock BUY must reject non-positive entry/stop/target prices even when
   the ordering and ratio look valid.

Each test is a safety assertion (not xfail). A failure here is a confirmed
defect to be fixed in production code in a later, approved stage.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import R3, evaluate, make_buy, make_portfolio, make_target, outcomes

# ---------------------------------------------------------------------------
# 1. Invalid final model rating
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_review_model_rating_never_approved_or_actionable():
    """A valid BUY proposal with model_rating="REVIEW" is never APPROVED/ACTIONABLE.

    The final PortfolioDecision is authoritative; an unusable rating must not be
    replaced by the Trader's BUY.
    """
    result = evaluate(make_buy(action="Buy", model_rating="REVIEW"))
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"


@pytest.mark.unit
def test_missing_model_rating_never_approved_or_actionable():
    """A missing final model rating is not substituted with the Trader's BUY."""
    result = evaluate(make_buy(action="Buy", model_rating=None))
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"


@pytest.mark.unit
def test_unrecognized_model_rating_never_approved_or_actionable():
    """An unrecognized final model rating cannot be approved."""
    result = evaluate(make_buy(action="Buy", model_rating="Strong Buy!!"))
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"


# ---------------------------------------------------------------------------
# 2. Inconsistent sector classification
# ---------------------------------------------------------------------------

# Consistent book: AAPL 20,000 (Technology) + MSFT 280,000 (Technology) + cash
# 700,000 = 1,000,000. AAPL target weight 0.05 -> projected AAPL 50,000.
# Projected Technology = 300,000 - 20,000 + 50,000 = 330,000 = 33% > 30%.
_SECTOR_BOOK = make_portfolio(
    holdings=[
        {"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
        {"ticker": "MSFT", "market_value": 280_000.0, "sector": "Technology"},
    ],
    cash=700_000.0,
    portfolio_value=1_000_000.0,
)


@pytest.mark.unit
def test_conflicting_target_sector_does_not_allow_approval():
    """A target sector ('Energy') conflicting with the real 33% Technology book
    must not allow APPROVED; the sector rule must record a non-PASS outcome."""
    data = make_buy(portfolio=_SECTOR_BOOK, target_position=make_target(0.05, sector="Energy"))
    result = evaluate(data)
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"
    # The affected-sector rule must not silently PASS on the wrong classification.
    assert outcomes(result).get(R3) != "PASS"


@pytest.mark.unit
@pytest.mark.parametrize(
    "variant",
    ["technology", "TECHNOLOGY", " Technonlogy ", "Technology "],
    ids=["lowercase", "uppercase", "typo_ws", "trailing_ws"],
)
def test_sector_name_variations_cannot_bypass_r3(variant):
    """Harmless case/whitespace variations must not let a 33% sector pass R3.

    Variants that still name Technology (case/whitespace) must be treated the
    same as the canonical spelling, so the 33% exposure is caught. A misspelling
    must not silently PASS either.
    """
    data = make_buy(portfolio=_SECTOR_BOOK, target_position=make_target(0.05, sector=variant))
    result = evaluate(data)
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"


# ---------------------------------------------------------------------------
# 3. Non-positive stock prices
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_negative_prices_with_valid_ordering_not_approved():
    """entry=-100, stop=-110, target=-70 (ordering OK, RR=3) must not be approved."""
    result = evaluate(make_buy(entry_price=-100.0, stop_loss=-110.0, price_target=-70.0))
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"


@pytest.mark.unit
@pytest.mark.parametrize(
    "entry, stop, target",
    [
        (0.0, -10.0, 30.0),      # zero entry
        (100.0, 0.0, 130.0),     # zero stop
        (100.0, 90.0, 0.0),      # zero target
        (0.0, 0.0, 0.0),         # all zero
    ],
    ids=["zero_entry", "zero_stop", "zero_target", "all_zero"],
)
def test_zero_prices_not_approved(entry, stop, target):
    """Zero price fields cannot yield an approved long BUY."""
    result = evaluate(make_buy(entry_price=entry, stop_loss=stop, price_target=target))
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"
