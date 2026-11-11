"""Wrong-side stop/target and direction-aware reward-to-risk (FR-A1, §5.4).

For a long BUY the ordering must be stop < entry < target. A stop at or above
entry, or a target at or below entry, is rejected (R4 VIOLATED). Unsupported
short/SELL direction is not approved (recorded as pending team confirmation).
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import R4, evaluate, make_buy, make_target, violated_ids


@pytest.mark.unit
@pytest.mark.parametrize(
    "stop, target",
    [
        (100.0, 130.0),   # stop == entry
        (105.0, 130.0),   # stop above entry (wrong side)
        (90.0, 100.0),    # target == entry
        (90.0, 95.0),     # target below entry (wrong side)
    ],
    ids=["stop_eq_entry", "stop_above_entry", "target_eq_entry", "target_below_entry"],
)
def test_bad_ordering_is_rejected(stop, target):
    """FR-A1: long ordering stop<entry<target is required (R4 VIOLATED)."""
    result = evaluate(make_buy(stop_loss=stop, price_target=target))
    assert result.verdict == "REJECTED"
    assert R4 in violated_ids(result)


@pytest.mark.unit
def test_direction_aware_ratio_long_pass():
    """FR-A1: long RR = (target-entry)/(entry-stop); 100/90/130 -> 3.0 passes."""
    result = evaluate(make_buy(entry_price=100.0, stop_loss=90.0, price_target=130.0))
    assert result.verdict == "APPROVED"


@pytest.mark.unit
def test_short_or_sell_is_never_approved_pending_team_confirmation():
    """FR-A1 (§5.4, pending): an unsupported SELL/short must not be approved.

    This is a mandatory safety assertion, not an xfail: until the team confirms
    SELL risk-reducing criteria, a SELL without explicit existing-position and
    trade data must be NEEDS_REVIEW, never APPROVED.
    """
    data = make_buy(action="Sell", model_rating="Sell", entry_price=100.0,
                    stop_loss=110.0, price_target=80.0,
                    target_position=make_target(0.0))
    result = evaluate(data)
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"
