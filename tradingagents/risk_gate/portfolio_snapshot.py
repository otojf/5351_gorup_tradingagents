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


def normalize_sector(sector: str | None) -> str | None:
    """Canonical sector key: whitespace-stripped and case-folded, or ``None``.

    Case and whitespace variants of the same sector must compare equal so R3
    aggregates and compares them consistently (BUG-002). This is intentionally a
    strict normalization, not fuzzy matching: a misspelling stays a *different*
    key and must be treated as unresolvable, never guessed.
    """
    if sector is None:
        return None
    key = sector.strip().casefold()
    return key or None


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
    """The analyzed instrument's sector key, or ``None`` when it cannot be determined.

    Prefers the explicit sector from ``target_position``; when the instrument is
    already held, its recorded sector is a fallback. Returns the normalized key.
    Never inferred from prose or fetched from a network.
    """
    explicit = normalize_sector(explicit_sector)
    if explicit is not None:
        return explicit
    symbol = normalize_symbol(ticker)
    for h in snapshot.holdings:
        if normalize_symbol(h.ticker) == symbol:
            held = normalize_sector(h.sector)
            if held is not None:
                return held
    return None


def held_sector(snapshot: PortfolioRiskSnapshot, ticker: str) -> str | None:
    """The held ``ticker``'s own classification key, or ``None`` when not held/unclassified."""
    symbol = normalize_symbol(ticker)
    for h in snapshot.holdings:
        if normalize_symbol(h.ticker) == symbol:
            return normalize_sector(h.sector)
    return None


def sector_conflict(snapshot: PortfolioRiskSnapshot, ticker: str,
                    explicit_sector: str | None) -> bool:
    """Whether an explicit target sector contradicts the ticker's existing classification.

    Only meaningful for an already-held, classified ticker: a conflicting explicit
    sector must not be able to re-scope the exposure calculation (BUG-002).
    """
    explicit = normalize_sector(explicit_sector)
    if explicit is None:
        return False
    existing = held_sector(snapshot, ticker)
    return existing is not None and existing != explicit


def current_sector_value(snapshot: PortfolioRiskSnapshot, sector: str) -> float:
    """Sum of market values currently held in ``sector`` (normalized comparison)."""
    key = normalize_sector(sector)
    if key is None:
        return 0.0
    return sum(h.market_value for h in snapshot.holdings
               if normalize_sector(h.sector) == key)


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
