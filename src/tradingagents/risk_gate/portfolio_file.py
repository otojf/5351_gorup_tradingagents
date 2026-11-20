"""Load the caller-supplied FR-A1 account snapshot from a JSON file.

The file is illustrative test/demo data in the repository examples; it is not a
real account. It must be internally consistent so the gate can evaluate exposure
without inventing values.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import PortfolioRiskSnapshot, TargetPosition
from .portfolio_snapshot import SnapshotError, validate_snapshot


def load_risk_portfolio(path: str | Path, trade_date: str | None = None) -> dict:
    """Read and validate a risk-gate account snapshot.

    Returns the adapter-facing mapping ``{"snapshot": ..., "target_position": ...}``
    with only the parts present in the file. ``trade_date``, when given, must match
    ``snapshot.valuation_date``; rejecting early avoids spending LLM tokens on a
    run whose gate would fail closed.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"risk portfolio file {path} is not readable: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"risk portfolio file {path} must contain a JSON object")

    snapshot_data = raw.get("snapshot")
    target_data = raw.get("target_position")
    try:
        snapshot = (
            PortfolioRiskSnapshot.model_validate(snapshot_data)
            if snapshot_data is not None
            else None
        )
        target = (
            TargetPosition.model_validate(target_data)
            if target_data is not None
            else None
        )
    except ValidationError as exc:
        raise ValueError(f"risk portfolio file {path} is invalid: {exc}") from exc

    if snapshot is None and target is None:
        raise ValueError(
            f"risk portfolio file {path} must contain 'snapshot' and/or 'target_position'"
        )
    if snapshot is not None and trade_date is not None:
        try:
            validate_snapshot(snapshot, str(trade_date))
        except SnapshotError as exc:
            raise ValueError(f"risk portfolio file {path} is not usable: {exc}") from exc

    loaded = {}
    if snapshot is not None:
        loaded["snapshot"] = snapshot.model_dump()
    if target is not None:
        loaded["target_position"] = target.model_dump()
    return loaded
