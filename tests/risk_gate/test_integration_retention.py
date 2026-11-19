"""Integration acceptance: structured retention, audit persistence, downstream
consumers, checkpoint safety, and performance (FR-A1 §5.1, §5.5, §13).

[SAFETY] The gate reads structured objects without re-parsing Markdown; the audit
is persisted with the exposure inputs; blocked BUYs are not authorized downstream;
a pre-gate checkpoint re-evaluates on resume.
[PRESERVE] Rendered strings keep their baseline shape.

These run the **real graph** with the offline scripted model and the real engine.
Before integration coding the adapter/state keys are absent, so they fail (RED).
"""

from __future__ import annotations

import json
import time

import pytest

import tests.test_graph_end_to_end as e2e
from tests.risk_gate.test_decision_boundary import (
    RISK_PORTFOLIO,
    _buy_decision,
    _buy_proposal,
    _graph,
)


@pytest.fixture
def offline(tmp_path, monkeypatch):
    return e2e.offline.__wrapped__(monkeypatch, tmp_path)


def _state_log(graph, ticker="NVDA"):
    from pathlib import Path

    logs = sorted(Path(graph.config["results_dir"]).glob(
        f"{ticker}/TradingAgentsStrategy_logs/*.json"))
    assert logs, "no state log written"
    return json.loads(logs[-1].read_text())


# ---------------------------------------------------------------------------
# C. Structured data retention
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_both_structured_objects_reach_the_gate(tmp_path, monkeypatch, offline):
    """[SAFETY] Trader and PM structured objects are retained in state for the gate."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, _ = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert state.get("trader_proposal") is not None
    assert state.get("portfolio_decision") is not None
    assert state["trader_proposal"].action.value == "Buy"
    assert state["portfolio_decision"].rating.value == "Buy"


@pytest.mark.unit
def test_free_text_fallback_cannot_bypass_required_inputs(tmp_path, monkeypatch, offline):
    """[SAFETY] A non-structured run (no typed proposals) cannot be approved."""
    # structured=False -> the model never returns typed objects; the gate has no
    # structured inputs and must fail closed.
    graph = e2e._graph(tmp_path, monkeypatch, e2e.ScriptedModel(structured=False),
                       risk_portfolio=RISK_PORTFOLIO)
    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert state.get("risk_verdict") in ("NEEDS_REVIEW", "REJECTED")
    assert signal == "REVIEW"
    assert state.get("decision_status") != "ACTIONABLE"


@pytest.mark.unit
def test_validation_failure_is_non_actionable_with_audit(tmp_path, monkeypatch, offline):
    """[SAFETY] A validation failure yields a non-actionable result with an audit record."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(stop_loss=None), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, _ = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert state["decision_status"] in ("BLOCKED", "PENDING_REVIEW")
    audit = state.get("risk_evaluation")
    assert audit is not None
    assert audit.rule_results


# ---------------------------------------------------------------------------
# D. Audit persistence
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_audit_persisted_with_required_fields(tmp_path, monkeypatch, offline):
    """[NFR-A2] State log records rule ids/outcomes, snapshot, verdict, policy, UTC."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    graph.propagate("NVDA", e2e.TRADE_DATE)
    entry = _state_log(graph)

    audit = entry.get("risk_audit") or entry.get("risk_evaluation")
    assert audit is not None, "audit not persisted"
    assert entry.get("risk_verdict") == "APPROVED"
    assert audit["policy_version"] == "fr-a1-v1"
    assert audit["policy_hash"]
    assert audit["evaluated_at_utc"].endswith("Z")
    assert audit["rule_results"] and all("rule_id" in r and "outcome" in r
                                         for r in audit["rule_results"])
    assert audit["input_snapshot"]


@pytest.mark.unit
def test_audit_snapshot_includes_numeric_exposure_inputs(tmp_path, monkeypatch, offline):
    """[§5.3] The audit exposes the numbers that explain sector/position math."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    graph.propagate("NVDA", e2e.TRADE_DATE)
    entry = _state_log(graph)
    audit = entry.get("risk_audit") or entry.get("risk_evaluation")
    snap = audit["input_snapshot"]

    for key in ("target_position_weight", "portfolio_value", "cash", "target_sector"):
        assert key in snap, key
    assert snap["target_position_weight"] == 0.05


@pytest.mark.unit
def test_audit_has_no_credentials_or_prompts(tmp_path, monkeypatch, offline):
    """[NFR-SEC] The persisted audit stores no credentials or raw prompts."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    graph.propagate("NVDA", e2e.TRADE_DATE)
    entry = _state_log(graph)
    assert entry.get("risk_audit") or entry.get("risk_evaluation"), "audit not persisted"
    blob = json.dumps(entry).lower()
    for needle in ("api_key", "apikey", "secret", "password", "bearer", "authorization"):
        assert needle not in blob
    assert "prompt" not in blob


@pytest.mark.unit
@pytest.mark.parametrize("label, proposal, decision", [
    ("approved", _buy_proposal(), _buy_decision()),
    ("rejected", _buy_proposal(stop_loss=None), _buy_decision()),
    ("needs_review", _buy_proposal(), _buy_decision(price_target=None)),
])
def test_all_verdicts_are_audited(tmp_path, monkeypatch, offline, label, proposal, decision):
    """[NFR-A2] APPROVED, REJECTED and NEEDS_REVIEW all produce an audit record."""
    graph = _graph(tmp_path, monkeypatch, proposal, decision, risk_portfolio=RISK_PORTFOLIO)
    state, _ = graph.propagate("NVDA", e2e.TRADE_DATE)
    assert state.get("risk_evaluation") is not None
    assert _state_log(graph).get("risk_verdict") == state["risk_verdict"]


@pytest.mark.unit
def test_audit_persistence_failure_cannot_leave_actionable_signal(tmp_path, monkeypatch, offline):
    """[SAFETY] If audit persistence fails, an actionable signal must not stand."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(graph, "_log_state", boom)
    with pytest.raises(OSError):
        graph.propagate("NVDA", e2e.TRADE_DATE)


@pytest.mark.unit
def test_audit_failure_does_not_release_actionable_buy_on_stream(tmp_path, monkeypatch, offline):
    """[SAFETY] A durable-audit failure must not publish an actionable BUY.

    The approved boundary (ADR §14): **every** risk evaluation must establish its
    required durable audit before the Portfolio Manager publishes its effective
    final recommendation. If persistence fails, the recommendation must not be
    published as actionable.

    The Stage 2 adapter defines the durable writer ``risk_gate.adapter.persist_audit``.
    We patch that *actual* writer with ``raising=True`` (so a missing writer fails
    this test RED), record that it was invoked, and make it raise a real
    persistence error. The test then proves no actionable BUY is released: it must
    either raise closed, or never stream ``final_rating == "Buy"``.
    """
    from tradingagents.risk_gate import adapter

    calls = {"n": 0}

    def failing_writer(*a, **k):
        calls["n"] += 1
        raise OSError("audit store unavailable")

    # raises if the writer is absent -> RED before implementation.
    monkeypatch.setattr(adapter, "persist_audit", failing_writer, raising=True)

    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)

    released = []
    closed = False
    try:
        for _messages, chunk in graph.stream_run(
                graph.create_run_state("NVDA", e2e.TRADE_DATE), **graph.propagator.get_graph_args()):
            if chunk and "final_rating" in chunk:
                released.append((chunk.get("final_rating"), chunk.get("risk_verdict")))
    except OSError:
        closed = True

    # The failure injection must actually have executed.
    assert calls["n"] >= 1, "durable audit writer was never invoked; injection unused"
    # Safety: no actionable BUY may be published when persistence failed.
    for rating, verdict in released:
        assert not (rating == "Buy" and verdict == "APPROVED"), released
    if not closed:
        # If the run did not fail closed, it must not have approved anything.
        assert all(verdict != "APPROVED" for _rating, verdict in released), released


# ---------------------------------------------------------------------------
# E. Downstream consumers (reports, memory, model evidence)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_model_recommendation_preserved_as_evidence(tmp_path, monkeypatch, offline):
    """[SAFETY] The model rating is preserved and distinguishable from the signal."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(stop_loss=None), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert state["model_rating"] == "Buy"        # evidence
    assert signal == "REVIEW"                    # effective public signal
    assert state["model_rating"] != signal


@pytest.mark.unit
def test_blocked_buy_is_not_an_authorized_buy_in_report(tmp_path, monkeypatch, offline):
    """[SAFETY] A blocked BUY does not appear as an authorized BUY in the report header."""
    from tradingagents.reporting import write_report_tree

    graph = _graph(tmp_path, monkeypatch, _buy_proposal(stop_loss=None), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, _ = graph.propagate("NVDA", e2e.TRADE_DATE)
    report = write_report_tree(state, "NVDA", tmp_path / "report").read_text()

    assert "- Rating: REVIEW" in report
    assert "- Rating: Buy" not in report


@pytest.mark.unit
def test_blocked_buy_memory_rating_is_review(tmp_path, monkeypatch, offline):
    """[SAFETY] The memory log does not record a blocked BUY as a Buy position."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(stop_loss=None), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    graph.propagate("NVDA", e2e.TRADE_DATE)
    entries = [e for e in graph.memory_log.load_entries() if e["ticker"] == "NVDA"]
    assert entries, "no memory entry recorded"
    assert entries[-1]["rating"] == "REVIEW"


@pytest.mark.unit
def test_rendered_strings_unchanged(tmp_path, monkeypatch, offline):
    """[PRESERVE] Rendered Markdown for reports/memory keeps its baseline shape."""
    from tradingagents.agents.schemas import render_pm_decision, render_trader_proposal

    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, _ = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert render_trader_proposal(state["trader_proposal"]) == state["trader_investment_plan"]
    assert render_pm_decision(state["portfolio_decision"]) == state["final_trade_decision"]



# ---------------------------------------------------------------------------
# F. Checkpoint safety (actual resume + legacy-signature compatibility)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pre_gate_checkpoint_resumes_through_evaluation(tmp_path, monkeypatch, offline):
    """[SAFETY] A checkpoint created before the gate re-evaluates on resume.

    The graph is interrupted before the Portfolio Manager, checkpointing enabled;
    the resumed run must reach the gate and produce a verdict (not bypass it).
    """
    model = e2e.ScriptedModel(structured=True, fail_at=12)   # before the decision
    graph = e2e._graph(tmp_path, monkeypatch, model, checkpoint_enabled=True,
                       risk_portfolio=RISK_PORTFOLIO)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        graph.propagate("NVDA", e2e.TRADE_DATE)

    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert "risk_verdict" in state
    assert state["risk_verdict"] in ("APPROVED", "REJECTED", "NEEDS_REVIEW")
    assert signal == state.get("final_rating")


@pytest.mark.unit
def test_legacy_pre_gate_checkpoint_cannot_bypass_evaluation(tmp_path, monkeypatch, offline):
    """[SAFETY] A real checkpoint written under the legacy (pre-gate) signature is
    retrievable under that thread, but the gated graph uses a distinct signature and
    cannot retrieve it, so it starts fresh and evaluates risk.

    Uses the repository's real ``thread_id`` / ``get_checkpointer`` /
    ``checkpoint_step`` APIs. Not a substring check on a hash.
    """
    from tradingagents.graph.checkpointer import checkpoint_step, get_checkpointer, thread_id

    graph = e2e._graph(tmp_path, monkeypatch, e2e.ScriptedModel(structured=True),
                       checkpoint_enabled=True)
    gated_sig = graph._run_signature("stock", None)

    # The legacy signature is the pre-gate run signature: its markers without the
    # gate's own marker. After integration the gated signature differs from it; the
    # test fails RED until the gate adds its marker.
    legacy_sig = "|".join(p for p in gated_sig.split("|") if not p.startswith("risk_gate"))

    cache = graph.config["data_cache_dir"]
    legacy_tid = thread_id("NVDA", e2e.TRADE_DATE, legacy_sig)
    gated_tid = thread_id("NVDA", e2e.TRADE_DATE, gated_sig)

    # Write a real checkpoint under the legacy thread via the real saver.
    from langgraph.graph import END, START, StateGraph

    with get_checkpointer(cache, "NVDA") as saver:
        g = StateGraph(dict)
        g.add_node("noop", lambda s: {})
        g.add_edge(START, "noop")
        g.add_edge("noop", END)
        compiled = g.compile(checkpointer=saver)
        compiled.invoke({}, config={"configurable": {"thread_id": legacy_tid}})
        # Prove the legacy checkpoint is actually written and retrievable.
        assert saver.get_tuple({"configurable": {"thread_id": legacy_tid}}) is not None
        assert saver.get_tuple({"configurable": {"thread_id": gated_tid}}) is None

    # The legacy checkpoint is retrievable under its own signature.
    assert checkpoint_step(cache, "NVDA", e2e.TRADE_DATE, legacy_sig) is not None
    # The gated signature is distinct and cannot retrieve the legacy record.
    assert gated_sig != legacy_sig
    assert gated_tid != legacy_tid
    assert checkpoint_step(cache, "NVDA", e2e.TRADE_DATE, gated_sig) is None

    # The gated graph therefore starts fresh and evaluates risk before deciding.
    state, _ = graph.propagate("NVDA", e2e.TRADE_DATE)
    assert state.get("risk_verdict") in ("APPROVED", "REJECTED", "NEEDS_REVIEW")
    assert state.get("risk_evaluation") is not None


# ---------------------------------------------------------------------------
# G. Actual integration overhead (adapter conversion + evaluation + audit)
# ---------------------------------------------------------------------------


def _bench_adapter(iterations=200, audit_dir=None):
    """Measure the adapter's per-call overhead: input conversion + one evaluation
    + the required durable audit write, over repeated offline calls. Returns
    (p50, p95) in ms."""
    from tradingagents.risk_gate.adapter import apply_gate

    tp = _buy_proposal()
    pd = _buy_decision()
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        apply_gate("NVDA", e2e.TRADE_DATE, tp, pd, RISK_PORTFOLIO, audit_dir=audit_dir)
        samples.append((time.perf_counter() - start) * 1000.0)
    samples.sort()
    p50 = samples[len(samples) // 2]
    p95 = samples[int(0.95 * (len(samples) - 1))]
    return p50, p95


@pytest.mark.unit
def test_actual_adapter_overhead_p95_within_two_seconds(tmp_path):
    """[NFR-A1] The real gate-added overhead — adapter conversion, one evaluation,
    and the durable audit **written to a real temporary directory** — p95 <= 2000 ms."""
    audit_dir = tmp_path / "audit_bench"
    p50, p95 = _bench_adapter(iterations=200, audit_dir=audit_dir)
    print(f"\nrisk-gate adapter overhead (with durable audit): "
          f"p50={p50:.4f}ms p95={p95:.4f}ms n=200")
    assert p95 <= 2000.0, f"adapter p95={p95:.4f}ms exceeds 2000ms"
    # The benchmark actually exercised the durable write path.
    assert list(audit_dir.glob("risk_audit_*.json")), "benchmark skipped the durable audit"


@pytest.mark.unit
def test_gate_adds_no_external_network_calls(tmp_path, monkeypatch, offline):
    """[NFR-A1] Running the gate issues no additional external network calls.

    The suite's autouse socket guard is active; a run that reaches the gate to a
    verdict completes without any socket connect, so the gate adds none.
    """
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, _ = graph.propagate("NVDA", e2e.TRADE_DATE)
    assert state["risk_evaluation"] is not None


@pytest.mark.unit
def test_existing_full_run_still_reaches_a_decision(tmp_path, monkeypatch, offline):
    """[PRESERVE] The end-to-end run still produces a logged decision."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)
    assert state["final_trade_decision"].strip()
    assert signal
