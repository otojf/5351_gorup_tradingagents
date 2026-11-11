"""100 deterministic invalid fixtures with zero approvals (FR-A1, INV-A1).

Cases are simple, independent, reproducible parameterized descriptors (no fragile
dictionary-merging cross-products). Exactly 100 **distinct** fixtures are
exercised, covering R1-R6 including blacklist violations. Distinctness is
determined by the actual input payload and the policy (blacklist), excluding the
human-readable label.

Each case declares the rule it targets and the outcome that rule must record
(``VIOLATED`` or ``UNKNOWN``). The test asserts the *expected outcome against the
actual fixture values*:
- the verdict is never APPROVED and the decision is never ACTIONABLE;
- the expected rule id is present with the expected outcome;
- a ``VIOLATED`` expectation is in ``triggered_violation_ids``;
- an ``UNKNOWN`` expectation is NOT falsely recorded as ``VIOLATED``;
- ``triggered_violation_ids`` is a subset of ``evaluated_rule_ids``.

Every blacklist case explicitly blacklists the analyzed ticker (AAPL).
"""

from __future__ import annotations

import pytest

from tests.risk_gate._support import (
    R1,
    R2,
    R3,
    R4,
    R5,
    R6,
    evaluate,
    make_buy,
    make_portfolio,
    make_target,
    outcomes,
    violated_ids,
)


def _case(label, kwargs, rule, outcome, blacklist=None):
    """One invalid fixture descriptor.

    ``rule``/``outcome`` are the expected result for the targeted rule;
    ``blacklist`` (when set) injects that ticker set into the policy. Every
    blacklist case MUST include the analyzed ticker (AAPL) so R5 applies.
    """
    return {
        "label": label,
        "kwargs": kwargs,
        "rule": rule,
        "outcome": outcome,
        "blacklist": blacklist,
    }


# A consistent 1,000,000 book used by the affordability fixture. R2 (0.05 <= 0.10)
# and R3 (Technology 20% <= 30%) pass; only affordability blocks approval.
_AFFORDABILITY_PORTFOLIO = make_portfolio(
    holdings=[
        {"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
        {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        {"ticker": "JPM", "market_value": 300_000.0, "sector": "Financials"},
        {"ticker": "XOM", "market_value": 300_000.0, "sector": "Energy"},
        {"ticker": "PG", "market_value": 220_000.0, "sector": "Consumer Staples"},
    ],
    cash=10_000.0,
    portfolio_value=1_000_000.0,
)

# A consistent book where the analyzed ticker (AAPL) is unheld, used by R3 cases.
def _sector_book(tech_value):
    """AAPL unheld; Technology = ``tech_value`` (MSFT); cash funds the 50,000 buy."""
    cash = 60_000.0
    fin = 1_000_000.0 - (tech_value + cash)
    return make_portfolio(
        holdings=[
            {"ticker": "AAPL", "market_value": 0.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": tech_value, "sector": "Technology"},
            {"ticker": "JPM", "market_value": fin, "sector": "Financials"},
        ],
        cash=cash,
        portfolio_value=1_000_000.0,
    )


# ---------------------------------------------------------------------------
# Single-rule and input-integrity bases (each case independent)
# ---------------------------------------------------------------------------

# R1: missing stop -> R1 VIOLATED; R4 becomes UNKNOWN (not falsely VIOLATED).
_R1 = [
    _case("r1_missing_stop", {"stop_loss": None}, R1, "VIOLATED"),
]

# R2: single-name over the 10% cap. VALID_BUY holds AAPL 20,000 of 1,000,000;
# weights above 0.10 are over the cap (and all are genuine increases).
_R2 = [
    _case(f"r2_weight_{w:.4f}", {"target_position": make_target(w)}, R2, "VIOLATED")
    for w in (0.1001, 0.11, 0.15, 0.25, 0.50)
]

# R3: projected sector over 30%. AAPL is unheld; target weight 0.05 of a
# 1,000,000 book = 50,000; Technology = tech_value + projected AAPL.
_R3 = [
    _case(f"r3_tech_{int(tech)}", {"portfolio": _sector_book(tech)}, R3, "VIOLATED")
    for tech in (260_000.0, 280_000.0, 300_000.0)  # projected 31%, 33%, 35%
]

# R4: reward-to-risk below 1.5 and wrong-side stops/targets.
_R4 = [
    _case(f"r4_stop{int(s)}_target{int(t)}", {"stop_loss": s, "price_target": t}, R4, "VIOLATED")
    for s, t in [
        (90.0, 105.0),    # RR 0.5
        (90.0, 114.0),    # RR 1.4
        (100.0, 130.0),   # stop == entry
        (105.0, 130.0),   # stop above entry
        (90.0, 100.0),    # target == entry
        (90.0, 95.0),     # target below entry
    ]
]

# R5: blacklist. Each case blacklists the analyzed ticker (AAPL).
_R5 = [
    _case("r5_blacklist_aapl", {}, R5, "VIOLATED", blacklist=frozenset({"AAPL"})),
    _case("r5_blacklist_aapl_and_peer", {}, R5, "VIOLATED",
          blacklist=frozenset({"AAPL", "MSFT"})),
    _case("r5_blacklist_multi", {}, R5, "VIOLATED",
          blacklist=frozenset({"AAPL", "TSLA", "NVDA"})),
]

# R6: input integrity. These resolve to NEEDS_REVIEW with the referenced rule
# UNKNOWN; the assertion checks the rule is not falsely VIOLATED.
_R6 = [
    _case("r6_missing_target", {"price_target": None}, R4, "UNKNOWN"),
    _case("r6_missing_weight", {"target_position": None}, R2, "UNKNOWN"),
    _case("r6_missing_portfolio", {"portfolio": None}, R3, "UNKNOWN"),
    _case("r6_contradictory_dir", {"action": "Buy", "model_rating": "Sell"}, R6, "UNKNOWN"),
    _case("r6_entry_nan", {"entry_price": float("nan")}, R6, "UNKNOWN"),
    _case("r6_entry_inf", {"entry_price": float("inf")}, R6, "UNKNOWN"),
    _case("r6_unknown_sector", {"portfolio": make_portfolio(
        holdings=[{"ticker": "AAPL", "market_value": 20_000.0, "sector": None},
                  {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"}],
        cash=830_000.0, portfolio_value=1_000_000.0)}, R3, "UNKNOWN"),
    _case("r6_inconsistent_book", {"portfolio": make_portfolio(
        holdings=[{"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
                  {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"}],
        cash=10_000.0, portfolio_value=1_000_000.0)}, R6, "UNKNOWN"),
    _case("r6_stale_valuation", {"portfolio": make_portfolio(
        holdings=[{"ticker": "AAPL", "market_value": 20_000.0, "sector": "Technology"},
                  {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"}],
        cash=830_000.0, portfolio_value=1_000_000.0, valuation_date="2020-01-01")},
        R6, "UNKNOWN"),
    _case("r6_affordability",
          {"target_position": make_target(0.05), "portfolio": _AFFORDABILITY_PORTFOLIO},
          R6, "UNKNOWN"),
]


def _payload_key(case):
    """Distinctness key: the actual input payload plus the policy, not the label."""
    kwargs = case["kwargs"]
    # Represent the payload canonically; dict values (nested portfolio/target)
    # are normalised to a stable string so equal payloads dedupe regardless of key
    # order. NaN/inf are represented distinctly via repr.
    items = tuple(
        sorted((k, repr(v)) for k, v in kwargs.items())
    )
    blacklist = tuple(sorted(case["blacklist"])) if case["blacklist"] else None
    return (items, blacklist)


def _build_cases():
    """Assemble single-rule cases and add independent multi-rule cases to reach 100.

    Multi-rule cases are explicit combinations (not a fragile merge of arbitrary
    dicts): a weight-over-cap case combined with an independent stop/target
    violation always targets R2 as VIOLATED because the target_position fully
    specifies the weight and the stop/target fields do not overlap it.
    """
    cases = list(_R1) + list(_R2) + list(_R3) + list(_R4) + list(_R5) + list(_R6)

    # Independent combinations that add distinct payloads without merge collisions.
    # (a) over-cap weight + each R4 stop/target case (target_position is R2's own key,
    #     stop/target are R4's keys -> no overwrite).
    for i, r2 in enumerate(_R2):
        for j, r4 in enumerate(_R4):
            merged = dict(r2["kwargs"])
            merged.update(r4["kwargs"])
            cases.append(_case(f"r2xr4_{i}_{j}", merged, R2, "VIOLATED"))
    # (b) sector-over + each R4 case (portfolio from R3, stop/target from R4).
    for i, r3 in enumerate(_R3):
        for j, r4 in enumerate(_R4):
            merged = dict(r3["kwargs"])
            merged.update(r4["kwargs"])
            cases.append(_case(f"r3xr4_{i}_{j}", merged, R3, "VIOLATED"))
    # (c) blacklist + each R4 case (blacklist from R5; AAPL is the analyzed ticker).
    for i, r5 in enumerate(_R5):
        for j, r4 in enumerate(_R4):
            merged = dict(r4["kwargs"])
            cases.append(_case(f"r5xr4_{i}_{j}", merged, R5, "VIOLATED",
                               blacklist=r5["blacklist"]))
    # (d) over-cap weight + sector-over (target_position from R2, portfolio from
    #     R3 -> distinct keys). R2 is the targeted VIOLATED rule.
    for i, r2 in enumerate(_R2):
        for j, r3 in enumerate(_R3):
            merged = dict(r2["kwargs"])
            merged.update(r3["kwargs"])
            cases.append(_case(f"r2xr3_{i}_{j}", merged, R2, "VIOLATED"))
    # (e) blacklist + over-cap weight (blacklist from R5, weight from R2).
    for i, r5 in enumerate(_R5):
        for j, r2 in enumerate(_R2):
            merged = dict(r2["kwargs"])
            cases.append(_case(f"r5xr2_{i}_{j}", merged, R5, "VIOLATED",
                               blacklist=r5["blacklist"]))

    # Deduplicate by actual payload + policy, preserving first occurrence order.
    seen, unique = set(), []
    for case in cases:
        key = _payload_key(case)
        if key in seen:
            continue
        seen.add(key)
        unique.append(case)
    return unique


_ALL = _build_cases()
assert len(_ALL) >= 100, f"only {len(_ALL)} distinct invalid cases generated"
CASES = _ALL[:100]
assert len(CASES) == 100
assert len({_payload_key(c) for c in CASES}) == 100, "the 100 fixtures must be distinct"
assert any(c["rule"] == R5 for c in CASES), "blacklist must be in the 100"
assert any(c["outcome"] == "UNKNOWN" for c in CASES), "input-integrity must be in the 100"
assert {R1, R2, R3, R4, R5}.issubset({c["rule"] for c in CASES})


def _policy(case):
    if case["blacklist"] is None:
        return None
    rg = __import__("tradingagents.risk_gate", fromlist=["RiskPolicy"])
    return rg.RiskPolicy(blacklist=case["blacklist"])


@pytest.mark.unit
@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[f"{c['label']}_{i:03d}" for i, c in enumerate(CASES)],
)
def test_invalid_fixture_is_never_approved(case):
    """FR-A1/INV-A1: no invalid fixture is APPROVED; expected rule outcome holds."""
    result = evaluate(make_buy(**case["kwargs"]), policy=_policy(case))
    label = case["label"]

    assert result.verdict != "APPROVED", (label, case["kwargs"])
    assert result.decision_status != "ACTIONABLE", (label, case["kwargs"])

    outs = outcomes(result)
    assert outs.get(case["rule"]) == case["outcome"], (label, outs)

    if case["outcome"] == "VIOLATED":
        assert case["rule"] in violated_ids(result), label
        assert case["rule"] in result.triggered_violation_ids, label
    else:  # UNKNOWN must not be falsely recorded as VIOLATED
        assert case["rule"] not in violated_ids(result), label
        assert case["rule"] not in result.triggered_violation_ids, label

    assert set(result.triggered_violation_ids) <= set(result.evaluated_rule_ids)


@pytest.mark.unit
def test_zero_approvals_across_all_invalid_fixtures():
    """FR-A1: aggregate — 0 of 100 invalid fixtures approved."""
    approvals = [
        c["label"] for c in CASES
        if evaluate(make_buy(**c["kwargs"]), policy=_policy(c)).verdict == "APPROVED"
    ]
    assert approvals == [], f"invalid fixtures approved: {approvals}"


@pytest.mark.unit
def test_blacklist_cases_blacklist_the_analyzed_ticker():
    """FR-A1 R5: every blacklist fixture includes the analyzed ticker (AAPL).

    Also evaluates one blacklist case so this cannot pass while the gate is missing.
    """
    blacklist_cases = [c for c in CASES if c["blacklist"] is not None]
    assert blacklist_cases, "at least one blacklist case must be present"
    analyzed = make_buy()["ticker"].upper()
    for case in blacklist_cases:
        normalized = {t.upper() for t in case["blacklist"]}
        assert analyzed in normalized, (case["label"], case["blacklist"])
    # Engine must exist and reject the blacklisted analyzed ticker.
    result = evaluate(make_buy(**blacklist_cases[0]["kwargs"]), policy=_policy(blacklist_cases[0]))
    assert R5 in violated_ids(result)


@pytest.mark.unit
def test_all_rules_and_integrity_are_represented():
    """FR-A1: the 100 cases cover R1-R5 and input-integrity UNKNOWN outcomes.

    Also exercises the engine on a representative case, so this cannot pass
    while the gate is missing.
    """
    rules = {c["rule"] for c in CASES}
    assert {R1, R2, R3, R4, R5}.issubset(rules), rules
    assert any(c["rule"] == R6 or c["outcome"] == "UNKNOWN" for c in CASES)
    result = evaluate(make_buy(**CASES[0]["kwargs"]), policy=_policy(CASES[0]))
    assert result.verdict in ("APPROVED", "REJECTED", "NEEDS_REVIEW")
