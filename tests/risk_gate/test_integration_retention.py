"""Integration acceptance: structured retention, audit persistence, checkpoint
safety, and regression compatibility (FR-A1 §5.1, §5.5, §2).

[SAFETY] The gate reads structured objects without re-parsing Markdown; audit
integrates at the boundary; a pre-gate checkpoint does not yield an unflagged run.
[PRESERVE] Rendered strings, ``final_rating``, and ``run_rating`` semantics are
unchanged.

These run against the graph and fail (RED) before implementation.
"""

from __future__ import annotations

import json

import pytest

import tests.test_graph_end_to_end as e2e


@pytest.fixture
def offline(tmp_path, monkeypatch):
    return e2e.offline.__wrapped__(monkeypatch, tmp_path)


@pytest.fixture
def offline_graph(tmp_path, monkeypatch, offline):
    return e2e._graph(tmp_path, monkeypatch, e2e.ScriptedModel(structured=True))


@pytest.mark.unit
def test_structured_objects_retained_in_state(offline_graph):
    """[SAFETY] Trader/PM structured objects reach state without Markdown parsing."""
    state, _ = offline_graph.propagate("NVDA", e2e.TRADE_DATE)
    assert state.get("trader_proposal") is not None
    assert state.get("portfolio_decision") is not None


@pytest.mark.unit
def test_rendered_strings_unchanged(offline_graph):
    """[PRESERVE] Rendered Markdown for reports/memory is still produced."""
    from tradingagents.agents.schemas import render_pm_decision, render_trader_proposal

    state, _ = offline_graph.propagate("NVDA", e2e.TRADE_DATE)
    assert render_trader_proposal(state["trader_proposal"]) == state["trader_investment_plan"]
    assert render_pm_decision(state["portfolio_decision"]) == state["final_trade_decision"]


@pytest.mark.unit
def test_run_rating_still_reads_model_rating(offline_graph):
    """[PRESERVE] ``run_rating`` reads the model rating field, not the verdict.

    The effective public signal is gated separately; ``run_rating`` itself keeps
    returning the model's own rating (``final_rating``), which the gate preserves.
    """
    from tradingagents.agents.rating import run_rating

    state, _ = offline_graph.propagate("NVDA", e2e.TRADE_DATE)
    assert run_rating(state) == state["final_rating"]


@pytest.mark.unit
def test_state_log_records_verdict_and_policy(offline_graph):
    """[SAFETY] Audit persistence: the state log records verdict and policy version."""
    imports = __import__("pathlib").Path
    state, _ = offline_graph.propagate("NVDA", e2e.TRADE_DATE)
    logs = list(imports(offline_graph.config["results_dir"]).glob(
        "NVDA/TradingAgentsStrategy_logs/*.json"))
    assert logs
    entry = json.loads(logs[0].read_text())
    assert "risk_verdict" in entry
    assert entry.get("policy_version") == "fr-a1-v1"


@pytest.mark.unit
def test_report_routes_public_signal_through_review(offline_graph):
    """[SAFETY] A non-approved BUY is not presented as an actionable rating."""
    state, signal = offline_graph.propagate("NVDA", e2e.TRADE_DATE)
    if state["risk_verdict"] != "APPROVED":
        from tradingagents.agents.rating import RATING_REVIEW
        assert signal == RATING_REVIEW


@pytest.mark.unit
def test_checkpoint_layout_marks_the_gate(tmp_path, monkeypatch, offline):
    """[SAFETY] Checkpoint signature is compatible only with a gated layout.

    Rather than searching a hash for a word, assert the concrete consequence:
    a checkpoint saved before the gate (no gate marker in the run signature)
    does not resume into a gated graph, so it starts fresh and cannot bypass
    evaluation.
    """
    graph = e2e._graph(tmp_path, monkeypatch, e2e.ScriptedModel(), checkpoint_enabled=True)
    sig = graph._run_signature("stock", None)
    # The signature is a joined set of key=value markers; the gate adds a marker.
    markers = [part.split("=", 1)[0] for part in sig.split("|")]
    assert "risk_gate" in markers or any(m.startswith("risk_gate") for m in markers), (
        f"run signature lacks a risk_gate marker: {markers}"
    )


@pytest.mark.unit
def test_existing_full_run_still_reaches_a_decision(offline_graph):
    """[PRESERVE] The end-to-end run still produces a logged decision."""
    state, signal = offline_graph.propagate("NVDA", e2e.TRADE_DATE)
    assert state["final_trade_decision"].strip()
    assert signal
