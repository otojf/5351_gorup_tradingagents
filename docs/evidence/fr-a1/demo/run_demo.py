#!/usr/bin/env python3
"""Reproducible offline demonstration of the FR-A1 deterministic risk gate.

Runs the REAL implementation (``tradingagents.risk_gate``) on deterministic local
data. No network, no external API, no LLM. Two clearly-labelled sections:

  1. ADAPTER-LEVEL demonstrations  — call ``adapter.apply_gate`` directly. These
     show the core rule outcome vs the effective publication outcome for each
     scenario, including audit persistence.
  2. FULL-GRAPH integration check  — runs the real ``TradingAgentsGraph`` with the
     existing offline scripted model (``tests/test_graph_end_to_end.py``) and the
     supplied ``risk_portfolio``, proving the boundary end-to-end.

Usage (from the repository root)::

    python docs/evidence/fr-a1/demo/run_demo.py

The output is captured verbatim in ``demo-output.txt``.
"""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

# Make the repository root importable when this file is run as a plain script, so
# the full-graph section can reuse ``tests.test_graph_end_to_end``.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tradingagents.agents import schemas  # noqa: E402
from tradingagents.risk_gate import adapter as adapter_mod  # noqa: E402
from tradingagents.risk_gate.adapter import apply_gate  # noqa: E402

TICKER = "NVDA"
TRADE_DATE = "2026-01-09"

# Deterministic, internally consistent book:
#   portfolio_value = 1,000,000 = cash 830,000 + NVDA 20,000 + MSFT 150,000.
#   NVDA target weight 0.05 -> projected 50,000 (+30,000 increase, affordable);
#   projected Technology = 170,000 - 20,000 + 50,000 = 200,000 (20% <= 30%).
VALID_PORTFOLIO = {
    "snapshot": {
        "valuation_date": TRADE_DATE,
        "portfolio_value": 1_000_000.0,
        "cash": 830_000.0,
        "holdings": [
            {"ticker": "NVDA", "market_value": 20_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
    },
    "target_position": {"target_position_weight": 0.05, "sector": "Technology"},
}

# A book whose real Technology exposure is 300,000 (30%); buying NVDA at 0.05
# pushes projected Technology to 350,000 (35%). A conflicting target sector
# ("Energy") must NOT be allowed to re-scope this into a false pass.
CONFLICTING_SECTOR_PORTFOLIO = {
    "snapshot": {
        "valuation_date": TRADE_DATE,
        "portfolio_value": 1_000_000.0,
        "cash": 700_000.0,
        "holdings": [
            {"ticker": "NVDA", "market_value": 0.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 300_000.0, "sector": "Technology"},
        ],
    },
    "target_position": {"target_position_weight": 0.05, "sector": "Energy"},
}


def buy_proposal(**overrides) -> schemas.TraderProposal:
    defaults = {"action": schemas.TraderAction.BUY, "reasoning": "deterministic demo",
                "entry_price": 100.0, "stop_loss": 90.0, "position_sizing": None}
    defaults.update(overrides)
    return schemas.TraderProposal(**defaults)


def buy_decision(**overrides) -> schemas.PortfolioDecision:
    defaults = {"rating": schemas.PortfolioRating.BUY, "executive_summary": "demo",
                "investment_thesis": "demo thesis", "price_target": 130.0}
    defaults.update(overrides)
    return schemas.PortfolioDecision(**defaults)


def _rule_summary(evaluation) -> str:
    non_pass = {r.rule_id: str(r.outcome) for r in evaluation.rule_results
                if str(r.outcome) != "PASS"}
    unknown = sorted(k for k, v in non_pass.items() if v == "UNKNOWN")
    violated = sorted(k for k, v in non_pass.items() if v == "VIOLATED")
    parts = []
    if violated:
        parts.append("VIOLATED=" + ",".join(violated))
    if unknown:
        parts.append("UNKNOWN=" + ",".join(unknown))
    return "; ".join(parts) or "all PASS"


def run_adapter_case(label, trader_proposal, portfolio_decision, risk_portfolio,
                     *, use_audit_dir=True, writer=None):
    """Run one adapter-level scenario, print a structured record, and return it.

    Returns a dict describing the observed outcome (including whether the writer
    raised), so the caller can assert the expected behaviour for each scenario.
    """
    risk_portfolio = copy.deepcopy(risk_portfolio)
    tmp = Path(tempfile.mkdtemp(prefix="fr-a1-demo-"))
    audit_dir = (tmp / "risk_audit") if use_audit_dir else None

    writer_calls = {"n": 0}
    saved_writer = None
    if writer is not None:
        saved_writer = adapter_mod.persist_audit

        def counting_writer(*args, **kwargs):
            writer_calls["n"] += 1
            return writer(*args, **kwargs)

        adapter_mod.persist_audit = counting_writer
    try:
        try:
            gate = apply_gate(TICKER, TRADE_DATE, trader_proposal, portfolio_decision,
                              risk_portfolio, audit_dir=audit_dir)
        except Exception as exc:  # noqa: BLE001 - a fail-closed raise is a valid outcome
            wrote = bool(audit_dir and list(audit_dir.glob("risk_audit_*.json")))
            print(f"\n[{label}]")
            print(f"  original model rating : {getattr(getattr(portfolio_decision,'rating',None),'value',None)}")
            print("  core rule verdict     : (not published)")
            print("  effective risk_verdict: (raised)")
            print("  final public rating   : (raised)")
            print("  decision status       : (raised)")
            print("  rules                 : fail-closed exception")
            print(f"  audit persisted       : {wrote}")
            print(f"  writer invoked        : {writer_calls['n']} time(s)")
            print(f"  outcome               : RAISED {type(exc).__name__}: {exc}")
            return {
                "raised": True,
                "exc_type": type(exc).__name__,
                "audit_written": wrote,
                "writer_calls": writer_calls["n"],
            }

        ev = gate["risk_evaluation"]
        wrote = bool(audit_dir and list(audit_dir.glob("risk_audit_*.json")))
        print(f"\n[{label}]")
        print(f"  original model rating : {gate['model_rating']}")
        print(f"  core rule verdict     : {ev.verdict} / {ev.decision_status}")
        print(f"  effective risk_verdict: {gate['risk_verdict']}")
        print(f"  final public rating   : {gate['final_rating']}")
        print(f"  decision status       : {gate['decision_status']}")
        print(f"  rules                 : {_rule_summary(ev)}")
        print(f"  triggered violations  : {ev.triggered_violation_ids}")
        print(f"  audit persisted       : {wrote}")
        print(f"  audit policy_version  : {ev.policy_version}  hash={ev.policy_hash[:12]}...")
        return {
            "raised": False,
            "core_verdict": ev.verdict,
            "core_status": ev.decision_status,
            "risk_verdict": gate["risk_verdict"],
            "final_rating": gate["final_rating"],
            "decision_status": gate["decision_status"],
            "violations": list(ev.triggered_violation_ids),
            "audit_written": wrote,
            "writer_calls": writer_calls["n"],
        }
    finally:
        if saved_writer is not None:
            adapter_mod.persist_audit = saved_writer


_CASES: list[dict] = []
_FAILURES: list[str] = []


def check(case_id: str, label: str, condition: bool, detail: str) -> None:
    """Record and print one expected-behaviour check."""
    status = "PASS" if condition else "FAIL"
    print(f"  check {case_id}: {status} — {detail}")
    _CASES.append({"id": case_id, "label": label, "passed": condition, "detail": detail})
    if not condition:
        _FAILURES.append(f"{case_id}: {detail}")


def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def adapter_demo() -> bool:
    section("SECTION 1 — ADAPTER-LEVEL DEMONSTRATIONS (real engine + adapter)")

    a = run_adapter_case("A. Valid BUY with complete risk inputs",
                         buy_proposal(), buy_decision(), VALID_PORTFOLIO)
    check("A", "valid BUY", not a["raised"]
          and a.get("core_verdict") == "APPROVED"
          and a.get("decision_status") == "ACTIONABLE",
          "core APPROVED and decision ACTIONABLE")

    b = run_adapter_case("B. BUY without stop-loss",
                         buy_proposal(stop_loss=None), buy_decision(), VALID_PORTFOLIO)
    check("B", "missing stop-loss", not b["raised"]
          and b.get("risk_verdict") == "REJECTED"
          and "R1_STOP_LOSS_REQUIRED" in b.get("violations", []),
          "REJECTED with R1 violation")

    c = run_adapter_case("C. BUY without portfolio snapshot",
                         buy_proposal(), buy_decision(), None)
    check("C", "missing snapshot", not c["raised"]
          and c.get("risk_verdict") == "NEEDS_REVIEW"
          and c.get("decision_status") == "PENDING_REVIEW",
          "NEEDS_REVIEW / PENDING_REVIEW")

    over_cap = {
        "snapshot": VALID_PORTFOLIO["snapshot"],
        "target_position": {"target_position_weight": 0.12, "sector": "Technology"},
    }
    d = run_adapter_case("D. Single-name concentration over 10% (12%)",
                         buy_proposal(), buy_decision(), over_cap)
    check("D", "single-name cap", not d["raised"]
          and d.get("risk_verdict") == "REJECTED"
          and "R2_SINGLE_NAME_CAP" in d.get("violations", []),
          "REJECTED with R2 violation")

    e = run_adapter_case("E. Conflicting sector classification (Energy vs real Technology)",
                         buy_proposal(), buy_decision(), CONFLICTING_SECTOR_PORTFOLIO)
    check("E", "conflicting sector", not e["raised"]
          and e.get("risk_verdict") != "APPROVED"
          and e.get("decision_status") != "ACTIONABLE",
          "not approved (non-actionable)")

    def failing_writer(*args, **kwargs):
        raise OSError("audit store unavailable")

    f = run_adapter_case("F. Audit persistence failure",
                         buy_proposal(), buy_decision(), VALID_PORTFOLIO,
                         writer=failing_writer)
    check("F", "audit writer failure", f["raised"]
          and f.get("exc_type") == "OSError"
          and f.get("writer_calls", 0) >= 1
          and not f.get("audit_written"),
          "writer invoked, raised, no audit written")

    g = run_adapter_case("G. No audit destination (would-be APPROVED downgraded)",
                         buy_proposal(), buy_decision(), VALID_PORTFOLIO,
                         use_audit_dir=False)
    check("G", "no audit destination", not g["raised"]
          and g.get("core_verdict") == "APPROVED"
          and g.get("decision_status") != "ACTIONABLE"
          and g.get("final_rating") == "REVIEW"
          and not g.get("audit_written"),
          "core APPROVED but publication non-actionable, no audit")

    return not _FAILURES


def full_graph_demo() -> bool:
    section("SECTION 2 — FULL-GRAPH INTEGRATION (real graph, offline scripted model)")
    try:
        import pytest

        import tests.test_graph_end_to_end as e2e
        from tradingagents.agents import schemas as s

        structured = dict(e2e.STRUCTURED)
        structured[s.TraderProposal] = buy_proposal()
        structured[s.PortfolioDecision] = buy_decision()
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(e2e, "STRUCTURED", structured, raising=False)
            tmp = Path(tempfile.mkdtemp(prefix="fr-a1-graph-"))
            # Reuse the suite's offline fixture to serve all tools locally.
            e2e.offline.__wrapped__(mp, tmp)
            graph = e2e._graph(tmp, mp, e2e.ScriptedModel(structured=True),
                               risk_portfolio=VALID_PORTFOLIO)
            state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)
        finally:
            mp.undo()
        print("\n[Full graph: valid BUY + complete risk_portfolio]")
        print(f"  propagate signal (effective) : {signal}")
        print(f"  state['model_rating']        : {state.get('model_rating')}")
        print(f"  state['risk_verdict']        : {state.get('risk_verdict')}")
        print(f"  state['decision_status']     : {state.get('decision_status')}")
        print(f"  both structured objects kept : "
              f"trader_proposal={state.get('trader_proposal') is not None}, "
              f"portfolio_decision={state.get('portfolio_decision') is not None}")
        check("FG", "full-graph valid BUY",
              signal == "Buy"
              and state.get("model_rating") == "Buy"
              and state.get("risk_verdict") == "APPROVED"
              and state.get("decision_status") == "ACTIONABLE"
              and state.get("trader_proposal") is not None
              and state.get("portfolio_decision") is not None,
              "signal Buy, system APPROVED/ACTIONABLE, both structured objects kept")
        return not _FAILURES
    except Exception as exc:  # noqa: BLE001
        # A failure here is a real failure of the integration demonstration, not a
        # success: report it and make the exit code non-zero.
        print(f"\n[Full graph] FAILED to run: {type(exc).__name__}: {exc}")
        check("FG", "full-graph valid BUY", False,
              f"full-graph demonstration raised {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    adapter_ok = adapter_demo()
    graph_ok = full_graph_demo()
    print("\n" + "-" * 78)
    print("Legend: 'core rule verdict' = risk_evaluation.verdict (policy outcome).")
    print("        'effective risk_verdict' = publication authorization.")
    print("        APPROVED core rules do not authorize publication without a")
    print("        durable audit; missing audit dir downgrades to NEEDS_REVIEW.")
    print("-" * 78)
    total = len(_CASES)
    passed = sum(1 for c in _CASES if c["passed"])
    print(f"\nSUMMARY: {passed}/{total} expectancy checks passed "
          f"(adapter={'PASS' if adapter_ok else 'FAIL'}, "
          f"full_graph={'PASS' if graph_ok else 'FAIL'}).")
    if _FAILURES:
        print("FAILURES:")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print("RESULT: all demonstrations passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
