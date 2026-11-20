"""Adapter safety edges: durable-audit destination, missing Trader action, and
malformed caller inputs (FR-A1 Stage 2 review, gaps 1-3).

These are test-first: they encode the required behavior and are expected to fail
RED where the current adapter is unsafe. They use the adapter directly so the
failure is attributable to production code, not to a fake.

`apply_gate` must never return an ACTIONABLE recommendation unless a real durable
audit was written. Caller inputs are never trusted or invented.
"""

from __future__ import annotations

import pytest

from test.offline.risk_gate.test_decision_boundary import (
    RISK_PORTFOLIO,
    _buy_decision,
    _buy_proposal,
)

# ---------------------------------------------------------------------------
# 1. Durable audit destination
# ---------------------------------------------------------------------------


def _apply(**kwargs):
    from tradingagents.risk_gate.adapter import apply_gate
    return apply_gate("NVDA", "2026-01-09", _buy_proposal(), _buy_decision(),
                      RISK_PORTFOLIO, **kwargs)


@pytest.mark.unit
def test_approved_without_audit_destination_is_never_actionable():
    """[SAFETY] An APPROVED decision with no audit_dir cannot be ACTIONABLE.

    A valid BUY with a complete snapshot would be APPROVED, but without a durable
    audit destination it must not be published as actionable.
    """
    result = _apply(audit_dir=None)
    assert not (result["final_rating"] == "Buy"
                and result["decision_status"] == "ACTIONABLE"), result


@pytest.mark.unit
def test_unusable_audit_directory_cannot_silently_bypass_audit(tmp_path):
    """[SAFETY] An unusable audit directory must fail closed with an audit error."""
    from tradingagents.risk_gate.adapter import AuditPersistenceError

    # A path under an existing *file* cannot be a directory.
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    with pytest.raises(AuditPersistenceError):
        _apply(audit_dir=blocker / "audit")


@pytest.mark.unit
def test_approved_decision_persists_audit_before_publication(tmp_path):
    """[SAFETY] For an APPROVED decision the audit file exists after the call."""
    audit_dir = tmp_path / "audit"
    result = _apply(audit_dir=audit_dir)
    assert result["decision_status"] == "ACTIONABLE"
    files = list(audit_dir.glob("risk_audit_*.json"))
    assert files, "APPROVED decision published without a durable audit file"


@pytest.mark.unit
def test_failing_audit_writer_blocks_actionable_output(tmp_path, monkeypatch):
    """[SAFETY] If the durable writer fails, no actionable recommendation returns."""
    from tradingagents.risk_gate import adapter as adapter_mod

    def boom(*a, **k):
        raise OSError("audit store unavailable")

    monkeypatch.setattr(adapter_mod, "persist_audit", boom, raising=True)
    with pytest.raises(OSError):
        _apply(audit_dir=tmp_path / "audit")


@pytest.mark.unit
def test_ordinary_valid_audit_path_still_approves(tmp_path):
    """[SAFETY] A normal valid audit path remains capable of APPROVED."""
    result = _apply(audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] == "APPROVED"
    assert result["decision_status"] == "ACTIONABLE"
    assert result["final_rating"] == "Buy"
    assert list((tmp_path / "audit").glob("risk_audit_*.json"))


# ---------------------------------------------------------------------------
# 2. Missing structured Trader action
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_missing_trader_proposal_cannot_be_approved(tmp_path):
    """[SAFETY] A valid PortfolioDecision rating does not substitute for a missing
    TraderProposal. With a complete snapshot and valid BUY info, the run must not
    be APPROVED or ACTIONABLE."""
    from tradingagents.risk_gate.adapter import apply_gate
    result = apply_gate("NVDA", "2026-01-09", None, _buy_decision(), RISK_PORTFOLIO,
                        audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] != "APPROVED"
    assert result["decision_status"] != "ACTIONABLE"
    assert result["final_rating"] == "REVIEW"
    # The model rating remains available as evidence.
    assert result["model_rating"] == "Buy"


@pytest.mark.unit
def test_missing_trader_action_is_r6_unknown(tmp_path):
    """[SAFETY] A missing Trader action is reflected by R6 (input integrity) UNKNOWN."""
    from tradingagents.risk_gate.adapter import apply_gate
    result = apply_gate("NVDA", "2026-01-09", None, _buy_decision(), RISK_PORTFOLIO,
                        audit_dir=tmp_path / "audit")
    outcomes = {r.rule_id: str(r.outcome) for r in result["risk_evaluation"].rule_results}
    assert outcomes.get("R6_INPUT_INTEGRITY") == "UNKNOWN", outcomes


# ---------------------------------------------------------------------------
# 3. Malformed risk_portfolio handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("bad", [
    "not-a-dict",
    42,
    ["list", "not", "dict"],
], ids=["str", "int", "list"])
def test_non_dict_risk_portfolio_never_actionable(bad, tmp_path):
    """[SAFETY] A non-dict risk_portfolio never yields an ACTIONABLE result."""
    from tradingagents.risk_gate.adapter import apply_gate
    try:
        result = apply_gate("NVDA", "2026-01-09", _buy_proposal(), _buy_decision(), bad,
                            audit_dir=tmp_path / "audit")
    except Exception:
        return  # explicit fail-closed is acceptable; never ACTIONABLE
    assert result["decision_status"] != "ACTIONABLE", result


@pytest.mark.unit
@pytest.mark.parametrize("snapshot", [
    {"portfolio_value": "not-a-number", "cash": 1.0, "valuation_date": "2026-01-09", "holdings": []},
    {"portfolio_value": 100.0, "cash": 1.0, "valuation_date": "2026-01-09",
     "holdings": [{"ticker": "NVDA", "market_value": "x", "sector": "Technology"}]},
    {"cash": 1.0},  # missing portfolio_value/valuation_date
], ids=["bad_value_type", "bad_market_value", "missing_fields"])
def test_invalid_snapshot_schema_fails_closed_without_crashing(snapshot, tmp_path):
    """[SAFETY] An invalid snapshot schema yields an auditable NEEDS_REVIEW."""
    from tradingagents.risk_gate.adapter import apply_gate
    rp = {"snapshot": snapshot, "target_position": {"target_position_weight": 0.05,
                                                    "sector": "Technology"}}
    result = apply_gate("NVDA", "2026-01-09", _buy_proposal(), _buy_decision(), rp,
                        audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] == "NEEDS_REVIEW"
    assert result["decision_status"] == "PENDING_REVIEW"
    assert result["final_rating"] == "REVIEW"


@pytest.mark.unit
@pytest.mark.parametrize("target", [
    {"target_position_weight": "half", "sector": "Technology"},
    {"target_position_weight": -0.1, "sector": "Technology"},
    {"target_position_weight": 2.0, "sector": "Technology"},
    "not-a-dict",
], ids=["bad_str", "negative", "over_one", "not_dict"])
def test_malformed_target_position_fails_closed_without_crashing(target, tmp_path):
    """[SAFETY] A malformed target_position yields an auditable NEEDS_REVIEW."""
    from tradingagents.risk_gate.adapter import apply_gate
    rp = {"snapshot": RISK_PORTFOLIO["snapshot"], "target_position": target}
    result = apply_gate("NVDA", "2026-01-09", _buy_proposal(), _buy_decision(), rp,
                        audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] == "NEEDS_REVIEW"
    assert result["decision_status"] == "PENDING_REVIEW"


@pytest.mark.unit
def test_non_mapping_risk_portfolio_fails_closed():
    """[SAFETY] A non-mapping config value is ignored, not crashed on."""
    from tradingagents.risk_gate.adapter import apply_gate
    result = apply_gate("NVDA", "2026-01-09", _buy_proposal(), _buy_decision(),
                        "not-a-dict")
    assert result["risk_verdict"] == "NEEDS_REVIEW"
    assert result["final_rating"] == "REVIEW"


@pytest.mark.unit
def test_approved_hold_keeps_model_rating(tmp_path):
    """[SAFETY] An approved HOLD is NO_TRADE but still publishes the model rating."""
    from tradingagents.agents import schemas
    from tradingagents.risk_gate.adapter import apply_gate
    hold = _buy_proposal(action=schemas.TraderAction.HOLD, entry_price=None, stop_loss=None)
    decision = _buy_decision(rating=schemas.PortfolioRating.HOLD, price_target=None)
    result = apply_gate("NVDA", "2026-01-09", hold, decision, RISK_PORTFOLIO,
                        audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] == "APPROVED"
    assert result["decision_status"] == "NO_TRADE"
    assert result["final_rating"] == "Hold"


@pytest.mark.unit
def test_proposal_sizing_above_cap_is_rejected(tmp_path):
    """[SAFETY] The Trader's own 100% sizing cannot be approved by a 5% config."""
    from tradingagents.risk_gate.adapter import apply_gate
    result = apply_gate("NVDA", "2026-01-09",
                        _buy_proposal(position_sizing="100% of portfolio"),
                        _buy_decision(), RISK_PORTFOLIO, audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] == "REJECTED"
    assert result["final_rating"] == "REVIEW"


@pytest.mark.unit
def test_proposal_sizing_within_cap_is_approved(tmp_path):
    """A parseable in-cap sizing still allows an otherwise safe BUY."""
    from tradingagents.risk_gate.adapter import apply_gate
    result = apply_gate("NVDA", "2026-01-09",
                        _buy_proposal(position_sizing="6% of portfolio"),
                        _buy_decision(), RISK_PORTFOLIO, audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] == "APPROVED"
    assert result["final_rating"] == "Buy"


@pytest.mark.unit
def test_unparseable_proposal_sizing_cannot_be_approved(tmp_path):
    """[SAFETY] Vague free text is UNKNOWN, even with a good config snapshot."""
    from tradingagents.risk_gate.adapter import apply_gate
    result = apply_gate("NVDA", "2026-01-09",
                        _buy_proposal(position_sizing="about a third"),
                        _buy_decision(), RISK_PORTFOLIO, audit_dir=tmp_path / "audit")
    assert result["risk_verdict"] == "NEEDS_REVIEW"
    assert result["final_rating"] == "REVIEW"
