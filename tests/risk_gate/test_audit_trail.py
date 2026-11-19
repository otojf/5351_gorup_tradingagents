"""NFR-A2: audit trail completeness for every evaluation.

Every evaluation must be auditable with rule IDs and outcomes, a minimal input
snapshot, the verdict, policy version and hash, a UTC timestamp, and latency.
These assertions check required *values*, not merely that a field exists, and
that no credentials or raw prompts are stored.
"""

from __future__ import annotations

import re

import pytest

from tests.risk_gate._support import evaluate, make_buy

_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_FORBIDDEN_SUBSTRINGS = ("api_key", "apikey", "secret", "password", "bearer", "authorization")


@pytest.mark.unit
def test_every_evaluation_has_a_complete_audit_record():
    """NFR-A2: verdict, rule ids, snapshot, policy version+hash, timestamp, latency."""
    result = evaluate(make_buy())
    assert result.policy_version == "fr-a1-v1"
    assert isinstance(result.policy_hash, str) and len(result.policy_hash) >= 16
    assert _UTC_RE.match(result.evaluated_at_utc), result.evaluated_at_utc
    assert result.evaluated_at_utc.endswith("Z") or "+00:00" in result.evaluated_at_utc
    assert isinstance(result.latency_ms, float) and result.latency_ms >= 0.0
    assert result.input_snapshot, "input snapshot must not be empty"
    assert result.rule_results, "per-rule results must be recorded"
    assert result.verdict in ("APPROVED", "REJECTED", "NEEDS_REVIEW")


@pytest.mark.unit
def test_audit_rule_results_have_ids_and_outcomes():
    """NFR-A2: each rule result carries a non-empty base id and a valid outcome."""
    result = evaluate(make_buy(stop_loss=None))
    valid_outcomes = {"PASS", "VIOLATED", "NOT_APPLICABLE", "UNKNOWN"}
    assert result.rule_results
    for rr in result.rule_results:
        assert rr.rule_id.startswith("R")
        assert str(rr.outcome) in valid_outcomes


@pytest.mark.unit
def test_ten_evaluations_all_audited_with_matching_policy():
    """NFR-A2: 100% audit coverage; version and hash identical across evaluations."""
    seen_versions, seen_hashes = set(), set()
    for _ in range(10):
        result = evaluate(make_buy())
        assert result.input_snapshot
        assert result.rule_results
        seen_versions.add(result.policy_version)
        seen_hashes.add(result.policy_hash)
    assert seen_versions == {"fr-a1-v1"}
    assert len(seen_hashes) == 1


@pytest.mark.unit
def test_input_snapshot_is_value_bearing():
    """NFR-A2: the snapshot records the actual evaluated inputs, not a placeholder."""
    result = evaluate(make_buy(entry_price=100.0, stop_loss=90.0, price_target=130.0))
    blob = repr(result.input_snapshot)
    assert "100" in blob and "90" in blob and "130" in blob


@pytest.mark.unit
def test_audit_snapshot_has_no_credentials_or_prompts():
    """NFR-A2/NFR-SEC: the input snapshot holds no credentials or raw prompts."""
    result = evaluate(make_buy())
    blob = repr(result.input_snapshot).lower()
    for needle in _FORBIDDEN_SUBSTRINGS:
        assert needle not in blob
    for key in result.input_snapshot:
        assert "prompt" not in str(key).lower()
