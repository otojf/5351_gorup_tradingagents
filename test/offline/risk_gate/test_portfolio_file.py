"""FR-A1: the caller-supplied account snapshot is validated before a run."""

from __future__ import annotations

import json

import pytest

from tradingagents.risk_gate.portfolio_file import load_risk_portfolio

SNAPSHOT = {
    "valuation_date": "2026-01-09",
    "portfolio_value": 100000.0,
    "cash": 83000.0,
    "holdings": [
        {"ticker": "NVDA", "market_value": 2000.0, "sector": "Technology"},
        {"ticker": "MSFT", "market_value": 15000.0, "sector": "Technology"},
    ],
}
TARGET = {"target_position_weight": 0.05, "sector": "Technology"}


def _write(tmp_path, payload):
    path = tmp_path / "risk.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.unit
def test_loads_snapshot_and_target(tmp_path):
    loaded = load_risk_portfolio(_write(tmp_path, {"snapshot": SNAPSHOT, "target_position": TARGET}),
                                 trade_date="2026-01-09")
    assert loaded["snapshot"]["portfolio_value"] == 100000.0
    assert loaded["target_position"]["target_position_weight"] == 0.05


@pytest.mark.unit
def test_rejects_valuation_date_mismatch(tmp_path):
    with pytest.raises(ValueError, match="valuation_date"):
        load_risk_portfolio(_write(tmp_path, {"snapshot": SNAPSHOT}), trade_date="2026-01-10")


@pytest.mark.unit
def test_rejects_inconsistent_book(tmp_path):
    bad = {**SNAPSHOT, "cash": 1.0}
    with pytest.raises(ValueError, match="inconsistent"):
        load_risk_portfolio(_write(tmp_path, {"snapshot": bad}), trade_date="2026-01-09")


@pytest.mark.unit
def test_rejects_non_object_and_empty_input(tmp_path):
    with pytest.raises(ValueError, match="JSON object"):
        load_risk_portfolio(_write(tmp_path, [1, 2, 3]))
    with pytest.raises(ValueError, match="must contain"):
        load_risk_portfolio(_write(tmp_path, {}))
