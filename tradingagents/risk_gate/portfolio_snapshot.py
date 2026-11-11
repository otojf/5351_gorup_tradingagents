"""Portfolio snapshot consistency and projected exposure (FR-A1 §5.3).

Under the documented cash-funded long assumption:

    projected_stock_value  = target_weight * portfolio_value
    projected_sector_value = current_sector_value - current_stock_value
                             + projected_stock_value

Exposure uses current **market values**, never average cost. This module returns
``None`` (with a reason) whenever the snapshot cannot be trusted, so the caller can
record ``UNKNOWN`` rather than invent a value.

Pure arithmetic: no network, file I/O, LLM, or LangGraph import.
"""

from __future__ import annotations

import math

from tradingagents.dataflows.symbols import normalize_symbol

from .models import PortfolioRiskSnapshot
from .sizing import projected_stock_value

# Currency-scale tolerance for the book identity; market values are floats.
_CONSISTENCY_TOLERANCE = 1.0  # one unit of the quote currency


class SnapshotError(Exception):
    """A snapshot that cannot be used: missing parts, inconsistent, or stale."""


def _finite(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
               for v in values)


def validate_snapshot(snapshot: PortfolioRiskSnapshot | None, trade_date: str) -> None:
    """Raise :class:`SnapshotError` when the snapshot is not usable.

    Checks presence, finiteness, the book identity
    ``cash + sum(market_value) == portfolio_value``, and that the valuation date
    matches the run's trade date.
    """
    if snapshot is None:
        raise SnapshotError("portfolio risk snapshot is missing")
    if not snapshot.valuation_date:
        raise SnapshotError("valuation_date is missing")
    if snapshot.valuation_date != trade_date:
        raise SnapshotError(
            f"valuation_date {snapshot.valuation_date!r} does not match trade_date {trade_date!r}"
        )
    if not _finite(snapshot.portfolio_value, snapshot.cash):
        raise SnapshotError("portfolio_value or cash is not finite")
    if snapshot.portfolio_value <= 0.0:
        raise SnapshotError("portfolio_value must be positive")
    for h in snapshot.holdings:
        if not _finite(h.market_value):
            raise SnapshotError(f"holding {h.ticker!r} market_value is not finite")
        if h.market_value < 0.0:
            raise SnapshotError(f"holding {h.ticker!r} market_value is negative")
    total = snapshot.cash + sum(h.market_value for h in snapshot.holdings)
    if abs(total - snapshot.portfolio_value) > _CONSISTENCY_TOLERANCE:
        raise SnapshotError(
            f"book is inconsistent: cash+holdings={total!r} != portfolio_value="
            f"{snapshot.portfolio_value!r}"
        )


def current_stock_value(snapshot: PortfolioRiskSnapshot, ticker: str) -> float:
    """The current market value held in ``ticker`` (0.0 when not held)."""
    symbol = normalize_symbol(ticker)
    return sum(h.market_value for h in snapshot.holdings if normalize_symbol(h.ticker) == symbol)


def target_sector(snapshot: PortfolioRiskSnapshot, ticker: str, explicit_sector: str | None) -> str | None:
    """The analyzed instrument's sector, or ``None`` when it cannot be determined.

    Prefers the explicit sector from ``target_position``; when the instrument is
    already held, its recorded sector is a fallback. Never inferred from prose.
    """
    if explicit_sector:
        return explicit_sector
    symbol = normalize_symbol(ticker)
    for h in snapshot.holdings:
        if normalize_symbol(h.ticker) == symbol and h.sector:
            return h.sector
    return None


def current_sector_value(snapshot: PortfolioRiskSnapshot, sector: str) -> float:
    """Sum of market values currently held in ``sector``."""
    return sum(h.market_value for h in snapshot.holdings if h.sector == sector)


def projected_sector_exposure(
    snapshot: PortfolioRiskSnapshot,
    ticker: str,
    sector: str,
    target_weight: float,
) -> float:
    """Projected post-trade sector exposure after a cash-funded buy to ``target_weight``.

    ``current_sector_value - current_stock_value + projected_stock_value``. The
    result is a *value*, not a fraction; the caller divides by ``portfolio_value``.
    """
    current_stock = current_stock_value(snapshot, ticker)
    current_sector = current_sector_value(snapshot, sector)
    projected_stock = projected_stock_value(target_weight, snapshot.portfolio_value)
    return current_sector - current_stock + projected_stock
