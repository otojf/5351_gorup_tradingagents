"""Projected single-name weight validation (FR-A1 §5.3).

The caller supplies ``target_position_weight`` explicitly; the gate never infers a
position from free-text sizing. This module decides whether a supplied weight is
usable and derives the projected market value from it under the cash-funded long
assumption.

Pure arithmetic: no network, file I/O, LLM, or LangGraph import.
"""

from __future__ import annotations

import math
import re
import unicodedata

_PERCENT = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:%|percent\b)", re.IGNORECASE)
_FRACTION = re.compile(
    r"(?<![\d.])(0?\.\d+)\s+(?:of\s+)?(?:the\s+)?(?:portfolio|book|account|position)\b",
    re.IGNORECASE,
)
_RANGE = re.compile(r"\d\s*(?:%|percent)?\s*(?:-|–|—|\bto\b)\s*\d", re.IGNORECASE)
_VAGUE = re.compile(
    r"\b(?:about|approximately|approx\.?|roughly|around|up to|at most|at least|"
    r"between|over|under)\b",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(r"(?<![\w.])-\s*\d")
_CONTEXT = re.compile(r"\b(?:portfolio|book|account|position)\b", re.IGNORECASE)


def parse_position_sizing(text: str | None) -> float | None:
    """Read one explicit portfolio percentage from the Trader's free text.

    Returns a fraction (``"5% of portfolio"`` -> ``0.05``) or ``None`` when the
    text is absent, vague, a range, negative, or not clearly a fraction of the
    portfolio. The gate may use a parsed value only to tighten or reject a
    caller-supplied target weight; it is never sufficient by itself to approve.
    """
    if not isinstance(text, str):
        return None
    normalized = unicodedata.normalize("NFKC", text).strip()
    if not normalized:
        return None
    if _VAGUE.search(normalized) or _RANGE.search(normalized) or _NEGATIVE.search(normalized):
        return None

    percents = _PERCENT.findall(normalized)
    if percents:
        if len(percents) != 1:
            return None
        bare = re.fullmatch(r"\d+(?:\.\d+)?\s*(?:%|percent)", normalized, re.IGNORECASE)
        if bare is None and _CONTEXT.search(normalized) is None:
            return None
        return float(percents[0]) / 100.0

    fractions = _FRACTION.findall(normalized)
    if len(fractions) == 1:
        return float(fractions[0])
    return None


def weight_problem(weight: float | None) -> str | None:
    """Return why ``weight`` is unusable, or ``None`` when it is a valid fraction.

    A usable weight is a finite number in the closed interval [0, 1]. Anything
    else (missing, NaN/inf, negative, above 1) is unusable and must not become an
    approval.
    """
    if weight is None:
        return "target_position_weight is missing"
    if not isinstance(weight, (int, float)) or isinstance(weight, bool):
        return "target_position_weight is not numeric"
    if isinstance(weight, float) and not math.isfinite(weight):
        return "target_position_weight is not finite"
    if weight < 0.0:
        return "target_position_weight is negative"
    if weight > 1.0:
        return "target_position_weight exceeds 100%"
    return None


def projected_stock_value(weight: float, portfolio_value: float) -> float:
    """The projected post-trade value of the analyzed instrument (cash-funded)."""
    return weight * portfolio_value
