"""INV-A1 invariants and boundary enforcement of the risk gate (FR-A1).

Bulk deterministic sweep: no APPROVED verdict may lack a stop-loss for an
actionable BUY, exceed the single-name cap, or claim ACTIONABLE while blocked.
"""

from __future__ import annotations

import itertools

import pytest

from tests.risk_gate._support import evaluate, make_buy, make_target


@pytest.mark.unit
def test_invariant_no_approval_without_stop_loss():
    """INV-A1: an actionable BUY is never APPROVED without a stop-loss."""
    for stop in (None, 90.0, 101.0):
        result = evaluate(make_buy(stop_loss=stop))
        if result.verdict == "APPROVED" and result.decision_status == "ACTIONABLE":
            assert stop is not None
    # The concrete violation case must not be approved at all.
    assert evaluate(make_buy(stop_loss=None)).verdict != "APPROVED"


@pytest.mark.unit
def test_invariant_no_approval_over_single_name_cap():
    """INV-A1: an APPROVED decision never exceeds the 10% single-name cap."""
    for weight in (0.0, 0.05, 0.10, 0.11, 0.25):
        result = evaluate(make_buy(target_position=make_target(weight)))
        if result.verdict == "APPROVED":
            assert weight <= 0.10


@pytest.mark.unit
def test_invariant_approved_implies_actionable_or_no_trade():
    """FR-A1 §5.2: APPROVED maps only to ACTIONABLE or NO_TRADE."""
    result = evaluate(make_buy())
    if result.verdict == "APPROVED":
        assert result.decision_status in ("ACTIONABLE", "NO_TRADE")


@pytest.mark.unit
def test_invariant_sweep_never_approves_violations():
    """INV-A1: sweep over invalid cases; zero approvals of any violating case."""
    stops = [None, 105.0, 90.0]
    targets = [95.0, 105.0, 130.0]
    weights = [0.05, 0.12]

    def violates(stop, target, weight):
        if stop is None or stop >= 100.0:
            return True
        if target <= stop or target <= 100.0:
            return True
        return weight > 0.10

    for stop, target, weight in itertools.product(stops, targets, weights):
        result = evaluate(
            make_buy(stop_loss=stop, price_target=target,
                     target_position=make_target(weight))
        )
        if violates(stop, target, weight):
            assert result.verdict != "APPROVED", (stop, target, weight)
