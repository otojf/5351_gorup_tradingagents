"""Trade-scope handling for HOLD and SELL/short (FR-A1, §5.4).

Mandatory safety properties (not xfail):
- HOLD is never ACTIONABLE.
- A SELL/short without explicit existing-position and trade data is not approved.

SELL risk-reducing criteria and exact HOLD rule exemptions remain PENDING team
confirmation; those expectations are documented here rather than silently
asserted. ``test_proposed_*`` tests are clearly marked as recording a proposal.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import evaluate, make_buy


@pytest.mark.unit
def test_hold_is_never_actionable():
    """FR-A1 §5.4 (mandatory): a HOLD is never an actionable trade."""
    data = make_buy(action="Hold", model_rating="Hold",
                    entry_price=None, stop_loss=None, price_target=None,
                    target_position=None, portfolio=None)
    result = evaluate(data)
    assert result.decision_status != "ACTIONABLE"


@pytest.mark.unit
def test_sell_without_position_data_is_not_approved():
    """FR-A1 §5.4 (mandatory): an unsupported SELL is never APPROVED."""
    data = make_buy(action="Sell", model_rating="Sell",
                    entry_price=None, stop_loss=None, price_target=None,
                    target_position=None, portfolio=None)
    result = evaluate(data)
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"


@pytest.mark.unit
def test_ambiguous_direction_is_not_approved():
    """FR-A1 §5.4 (mandatory): ambiguous direction is never APPROVED."""
    data = make_buy(action=None, model_rating=None, stop_loss=90.0, price_target=130.0)
    result = evaluate(data)
    assert result.verdict != "APPROVED"
    assert result.decision_status != "ACTIONABLE"


@pytest.mark.unit
@pytest.mark.xfail(
    strict=False,
    reason="PROPOSED P2: SELL with explicit existing-position+ trade data is evaluated as "
           "risk-reducing (exact criteria pending team confirmation). Proposal recorded only.",
)
def test_proposed_sell_with_position_data_is_evaluated():
    """PROPOSED P2: a documented SELL is evaluated (exact expectation TBD)."""
    data = make_buy(action="Sell", model_rating="Sell", entry_price=100.0,
                    stop_loss=110.0, price_target=80.0)
    result = evaluate(data)
    assert result.verdict in ("APPROVED", "NEEDS_REVIEW")
