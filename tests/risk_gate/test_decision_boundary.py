"""Integration acceptance: the risk verdict reaches the public decision boundary.

[SAFETY] A rejected or unreviewed BUY must not escape as an actionable final
recommendation, on either the programmatic API (``TradingAgentsGraph.propagate``)
or the CLI stream path. Assertions are unconditional for the expected verdict,
the effective public signal, and the preserved original model rating. Both
REJECTED and NEEDS_REVIEW are covered.

These run against the graph and CLI infrastructure and fail (RED) before
implementation because ``tradingagents.risk_gate`` does not exist yet.
"""

from __future__ import annotations

import pytest

import tests.test_graph_end_to_end as e2e
from tradingagents.agents.rating import RATING_REVIEW

# ---------------------------------------------------------------------------
# Programmatic API path
# ---------------------------------------------------------------------------


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """Reuse the end-to-end offline fixture (all vendors answered locally)."""
    return e2e.offline.__wrapped__(monkeypatch, tmp_path)


def _graph_for(tmp_path, monkeypatch, *proposals):
    """A graph whose scripted structured model returns the given proposals.

    ``proposals`` is a sequence of ``(Schema, instance)`` overrides layered on the
    end-to-end ``STRUCTURED`` mapping; only the overridden schemas differ.
    """
    model = e2e.ScriptedModel(structured=True)
    structured = dict(e2e.STRUCTURED)
    for schema, instance in proposals:
        structured[schema] = instance
    monkeypatch.setattr(e2e, "STRUCTURED", structured, raising=False)
    return e2e._graph(tmp_path, monkeypatch, model)


def _run_and_capture(tmp_path, monkeypatch, proposals):
    """Run propagate and return (state, public_signal)."""
    graph = _graph_for(tmp_path, monkeypatch, *proposals)
    return graph.propagate("NVDA", e2e.TRADE_DATE)


def _run_offline(graph):
    return graph.propagate("NVDA", e2e.TRADE_DATE)


@pytest.mark.unit
def test_rejected_buy_does_not_escape_as_actionable(tmp_path, monkeypatch, offline):
    """[SAFETY] API: a REJECTED BUY's public signal is REVIEW; model rating kept."""
    from tradingagents.agents import schemas

    proposals = [
        (schemas.TraderProposal, schemas.TraderProposal(
            action=schemas.TraderAction.BUY, reasoning="no stop supplied", stop_loss=None)),
        (schemas.PortfolioDecision, schemas.PortfolioDecision(
            rating=schemas.PortfolioRating.BUY, executive_summary="buy",
            investment_thesis="strong", price_target=130.0)),
    ]
    state, signal = _run_and_capture(tmp_path, monkeypatch, proposals)

    assert state["risk_verdict"] == "REJECTED"
    assert signal == RATING_REVIEW
    assert state["model_rating"] == "Buy"          # original recommendation preserved
    assert state["decision_status"] == "BLOCKED"


@pytest.mark.unit
def test_needs_review_buy_does_not_escape_as_actionable(tmp_path, monkeypatch, offline):
    """[SAFETY] API: a NEEDS_REVIEW BUY's public signal is REVIEW."""
    from tradingagents.agents import schemas

    proposals = [
        (schemas.TraderProposal, schemas.TraderProposal(
            action=schemas.TraderAction.BUY, reasoning="ambiguous", stop_loss=90.0,
            entry_price=100.0, position_sizing=None)),
        (schemas.PortfolioDecision, schemas.PortfolioDecision(
            rating=schemas.PortfolioRating.BUY, executive_summary="buy",
            investment_thesis="strong", price_target=None)),  # missing target -> R4 unknown
    ]
    state, signal = _run_and_capture(tmp_path, monkeypatch, proposals)

    assert state["risk_verdict"] == "NEEDS_REVIEW"
    assert signal == RATING_REVIEW
    assert state["model_rating"] == "Buy"
    assert state["decision_status"] == "PENDING_REVIEW"


# ---------------------------------------------------------------------------
# CLI stream path
# ---------------------------------------------------------------------------


class _RejectingFakeGraph:
    """Drives ``cli.run.run_analysis`` with a streamed REJECTED BUY decision.

    ``stream_run`` yields the same per-node chunks the real graph does, including
    an adjacent ``risk_verdict``/``model_rating``/``decision_status`` set as the
    gate node would, then ``record_decision`` receives the merged final state.
    """

    def __init__(self):
        self.graph = self
        self.propagator = self
        self._resuming = False
        self.recorded = None
        self.streamed_states = []

    def create_run_state(self, ticker, trade_date, asset_type="stock", portfolio=None):
        return {"messages": [], "company_of_interest": ticker, "trade_date": trade_date}

    def get_graph_args(self, callbacks=None):
        return {}

    def begin_checkpoint(self, *a, **k):
        return None

    def checkpoint_input(self, state):
        return state

    def clear_checkpoint_on_success(self, *a, **k):
        pass

    def end_checkpoint(self):
        pass

    def stream_run(self, graph_input, **kwargs):
        # Portfolio Manager output, then the Risk Gate node's verdict.
        pm = {
            "messages": [],
            "final_trade_decision": "**Rating**: Buy\n\nStrong.",
            "final_rating": "Buy",
            "model_rating": "Buy",
        }
        gate = {"risk_verdict": "REJECTED", "decision_status": "BLOCKED"}
        self.streamed_states = [pm, gate]
        for chunk in self.streamed_states:
            yield [], chunk

    def record_decision(self, ticker, trade_date, final_state):
        self.recorded = (ticker, trade_date, dict(final_state))


def _drive_cli(monkeypatch, tmp_path, fake):
    import cli.run as cli_run
    from cli.models import AnalystType

    class _Buffer:
        def __init__(self):
            self.messages = []
            self.tool_calls = []
            self.report_sections = {}
            self.agent_status = {}
            self.selected_analysts = []
            self._processed_message_ids = set()

        def init_for_analysis(self, selected):
            self.selected_analysts = [a.lower() for a in selected]

        def add_message(self, *a):
            pass

        def add_tool_call(self, *a):
            pass

        def update_report_section(self, *a):
            pass

        def update_agent_status(self, *a):
            pass

    class _NullLive:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    buffer = _Buffer()
    monkeypatch.setattr(cli_run, "TradingAgentsGraph", lambda *a, **k: fake)
    monkeypatch.setattr(cli_run, "message_buffer", buffer)
    monkeypatch.setattr(cli_run, "create_layout", lambda: None)
    monkeypatch.setattr(cli_run, "update_display", lambda *a, **k: None)
    monkeypatch.setattr(cli_run, "Live", _NullLive)
    monkeypatch.setattr(cli_run, "get_user_selections", lambda flags=None: {
        "ticker": "NVDA", "analysis_date": "2026-01-10",
        "analysts": [AnalystType.MARKET], "asset_type": "stock",
    })
    monkeypatch.setattr(cli_run, "_build_run_config", lambda selections, checkpoint: {
        "data_cache_dir": str(tmp_path / "cache"), "results_dir": str(tmp_path / "results"),
    })
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "N")
    cli_run.run_analysis()
    return buffer


@pytest.mark.unit
def test_cli_stream_path_blocks_rejected_buy(tmp_path, monkeypatch):
    """[SAFETY] CLI: a REJECTED BUY cannot escape as an actionable public decision."""
    from tradingagents.agents.rating import is_review, run_rating

    fake = _RejectingFakeGraph()
    _drive_cli(monkeypatch, tmp_path, fake)

    assert fake.recorded is not None, "CLI never recorded a decision"
    _ticker, _date, final_state = fake.recorded
    assert final_state["risk_verdict"] == "REJECTED"
    assert final_state["model_rating"] == "Buy"
    # The public signal the CLI would print/report must be REVIEW, not Buy.
    assert is_review(run_rating(final_state)) or final_state.get("decision_status") == "BLOCKED"
    assert final_state["decision_status"] == "BLOCKED"
