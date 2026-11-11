"""Deterministic builders and accessors for the FR-A1 contract.

The tests target the proposed interface in ``docs/req/fr-a1-test-plan.md``. The
production package ``tradingagents.risk_gate`` is not implemented yet. Importing
it here would make every module fail to import; instead each test imports the
engine itself (``require_engine``), so individual tests are collected before
implementation and fail honestly because the implementation is absent.
"""

from __future__ import annotations

import copy
import importlib


def require_engine():
    """The ``tradingagents.risk_gate`` package, or fail the calling test.

    Raises ``ModuleNotFoundError`` before implementation. This is a real failure
    (RED), not a skip: the mandatory FR-A1 safety tests must not be able to pass
    while the gate is missing.
    """
    return importlib.import_module("tradingagents.risk_gate")


# ---------------------------------------------------------------------------
# Deterministic, internally consistent input builders
# ---------------------------------------------------------------------------

VALID_TICKER = "AAPL"
VALID_DATE = "2026-01-09"

# A fully in-bounds, cash-funded long BUY with a completely consistent book.
#   portfolio_value = 1,000,000 = cash 830,000 + AAPL 20,000 + MSFT 150,000
#   entry 100, stop 90, target 130   -> risk 10, reward 30, RR 3.0
#   target_weight 0.05               -> projected AAPL value 50,000 (an increase
#                                       from 20,000; the 30,000 purchase is
#                                       affordable from 830,000 cash)
#   current Technology = AAPL 20,000 + MSFT 150,000 = 170,000 (17%)
#   projected Technology = 170,000 - 20,000 + 50,000 = 200,000 (20% <= 30%)
#   not blacklisted
VALID_BUY = {
    "ticker": VALID_TICKER,
    "trade_date": VALID_DATE,
    "action": "Buy",
    "entry_price": 100.0,
    "stop_loss": 90.0,
    "price_target": 130.0,
    "model_rating": "Buy",
    "target_position": {"target_position_weight": 0.05, "sector": "Technology"},
    "portfolio": {
        "valuation_date": VALID_DATE,
        "portfolio_value": 1_000_000.0,
        "cash": 830_000.0,
        "holdings": [
            {"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
    },
}


def deep_copy(data):
    """An independent deep copy of nested fixture data."""
    return copy.deepcopy(data)


def make_buy(**overrides):
    """A deep copy of VALID_BUY with top-level overrides applied.

    Nested dicts supplied in ``overrides`` replace the corresponding nested value
    wholesale; callers build those with ``make_portfolio``/``make_holding``.
    """
    data = deep_copy(VALID_BUY)
    data.update(overrides)
    return data


def make_holding(ticker, market_value, sector):
    return {"ticker": ticker, "market_value": market_value, "sector": sector}


def make_portfolio(holdings, cash, portfolio_value, valuation_date=VALID_DATE):
    return {
        "valuation_date": valuation_date,
        "portfolio_value": portfolio_value,
        "cash": cash,
        "holdings": list(holdings),
    }


def make_target(weight, sector="Technology"):
    return {"target_position_weight": weight, "sector": sector}


def evaluate(data, policy=None):
    """Run the pure engine on a builder dict, via the contract's models."""
    rg = require_engine()
    inputs = rg.RiskInputs.model_validate(data)
    if policy is None:
        return rg.evaluate_risk(inputs)
    return rg.evaluate_risk(inputs, policy)


def violated_ids(evaluation) -> set[str]:
    """Rule IDs whose outcome is VIOLATED (not UNKNOWN)."""
    return {r.rule_id for r in evaluation.rule_results if str(r.outcome) == "VIOLATED"}


def unknown_ids(evaluation) -> set[str]:
    """Rule IDs whose outcome is UNKNOWN (inputs insufficient to decide)."""
    return {r.rule_id for r in evaluation.rule_results if str(r.outcome) == "UNKNOWN"}


def outcomes(evaluation) -> dict[str, str]:
    return {r.rule_id: str(r.outcome) for r in evaluation.rule_results}


# ---------------------------------------------------------------------------
# Rule identifiers (single source for the tests)
# ---------------------------------------------------------------------------

R1 = "R1_STOP_LOSS_REQUIRED"
R2 = "R2_SINGLE_NAME_CAP"
R3 = "R3_SECTOR_CONCENTRATION"
R4 = "R4_REWARD_RISK"
R5 = "R5_BLACKLIST"
R6 = "R6_INPUT_INTEGRITY"
R0 = "R0_ALL_RULES_PASSED"
