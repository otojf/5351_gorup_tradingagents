"""Projected single-name weight validation (FR-A1 §5.3).

The caller supplies ``target_position_weight`` explicitly; the gate never infers a
position from free-text sizing. This module decides whether a supplied weight is
usable and derives the projected market value from it under the cash-funded long
assumption.

Pure arithmetic: no network, file I/O, LLM, or LangGraph import.
"""

from __future__ import annotations

import math


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
