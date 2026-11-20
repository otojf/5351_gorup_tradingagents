"""The golden set: fixed (ticker, date) cases the harness runs every time.

Three cases as NFR-E1 asks (3-5). Each case's ticker and date drive its own
scripted fixtures, so the run really analyses that instrument on that date.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    ticker: str
    trade_date: str
    asset_type: str = "stock"
    analysts: tuple[str, ...] = ("market", "social", "news", "fundamentals")
    portfolio: str | None = None
    expected_rating: str | None = None


GOLDEN_SET: list[GoldenCase] = [
    GoldenCase(
        case_id="nvda-2026-01-09",
        ticker="NVDA",
        trade_date="2026-01-09",
        expected_rating="Overweight",
    ),
    GoldenCase(
        case_id="aapl-2026-01-16",
        ticker="AAPL",
        trade_date="2026-01-16",
        expected_rating="Overweight",
    ),
    GoldenCase(
        case_id="msft-2026-01-23",
        ticker="MSFT",
        trade_date="2026-01-23",
        expected_rating="Overweight",
    ),
]
