"""FR-A1: free-text position sizing can tighten or reject, never approve."""

from __future__ import annotations

import pytest

from tradingagents.risk_gate.sizing import parse_position_sizing


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5% of portfolio", 0.05),
        ("100% of portfolio", 1.0),
        ("6%", 0.06),
        ("12.5 percent of the account", 0.125),
        ("0.05 of portfolio", 0.05),
        ("5% position", 0.05),
        ("buy 100 shares (5% of portfolio)", 0.05),
        ("5-10% of portfolio", None),
        ("about 5%", None),
        ("-5%", None),
        ("half the portfolio", None),
        ("5% stop-loss distance", None),
        ("a modest position", None),
        ("5% and 10%", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_position_sizing(text, expected):
    assert parse_position_sizing(text) == expected
