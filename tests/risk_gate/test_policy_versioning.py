"""Policy versioning and injectable blacklist (FR-A1 §5.5).

The policy is versioned (initially ``fr-a1-v1``) with a stable hash that changes
when a threshold changes. The blacklist is deterministic and injectable, and
ticker matching is normalization-consistent.
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import R5, evaluate, make_buy, violated_ids


@pytest.mark.unit
def test_default_policy_version_and_hash():
    """FR-A1 §5.5: default policy is fr-a1-v1 with a non-empty stable hash."""
    rg = __import__("tradingagents.risk_gate", fromlist=["RiskPolicy"])
    p1 = rg.RiskPolicy()
    p2 = rg.RiskPolicy()
    assert p1.version == "fr-a1-v1"
    assert p1.policy_hash and len(p1.policy_hash) >= 16
    assert p1.policy_hash == p2.policy_hash


@pytest.mark.unit
def test_hash_changes_when_a_threshold_changes():
    """FR-A1 §5.5: changing a threshold changes the policy hash."""
    rg = __import__("tradingagents.risk_gate", fromlist=["RiskPolicy"])
    base = rg.RiskPolicy()
    changed = rg.RiskPolicy(single_name_cap=0.20)
    assert base.policy_hash != changed.policy_hash


@pytest.mark.unit
def test_policy_version_reaches_evaluation():
    """FR-A1 §5.5: the evaluation records the policy version and hash."""
    result = evaluate(make_buy())
    assert result.policy_version == "fr-a1-v1"
    assert result.policy_hash


@pytest.mark.unit
@pytest.mark.parametrize("ticker", ["AAPL", "aapl", " Aapl "])
def test_blacklist_matches_after_normalization(ticker):
    """FR-A1 §5.5: blacklist matching is normalization-consistent."""
    rg = __import__("tradingagents.risk_gate", fromlist=["RiskPolicy"])
    result = evaluate(make_buy(ticker=ticker), policy=rg.RiskPolicy(blacklist=frozenset({"AAPL"})))
    assert result.verdict == "REJECTED"
    assert R5 in violated_ids(result)
