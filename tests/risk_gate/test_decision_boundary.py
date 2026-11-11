"""Integration acceptance: the risk verdict reaches the public decision boundary.

[SAFETY] A rejected or unreviewed BUY must not escape as an actionable final
recommendation, on either the programmatic API (``TradingAgentsGraph.propagate``)
or the CLI merge path. These run the **real graph** with the existing offline
scripted model and the real risk engine; the verdict is produced by the engine,
never mocked.

The gate is invoked once at the Portfolio Manager output boundary (ADR §13). The
caller supplies the structured snapshot and target weight via the additive
``risk_portfolio`` config key; when absent, inputs are incomplete and the gate
fails closed.

A valid in-bounds BUY is APPROVED via a complete supplied snapshot, so the suite
does not degenerate into "everything NEEDS_REVIEW". Before integration coding the
adapter/state keys are absent, so these fail (RED) honestly.
"""

from __future__ import annotations

import pytest

import tests.test_graph_end_to_end as e2e
from tradingagents.agents.rating import RATING_REVIEW

# ---------------------------------------------------------------------------
# Fixtures and helpers: real graph + structured proposals + supplied snapshot
# ---------------------------------------------------------------------------


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """Reuse the end-to-end offline fixture (all vendors answered locally)."""
    return e2e.offline.__wrapped__(monkeypatch, tmp_path)


# A complete, consistent snapshot for NVDA so an in-bounds BUY can be APPROVED.
#   portfolio_value = 1,000,000 = cash 830,000 + NVDA 20,000 + MSFT 150,000
#   NVDA target weight 0.05 -> projected 50,000 (+30,000 increase, affordable)
#   project. Technology = 170,000 - 20,000 + 50,000 = 200,000 (20% <= 30%)
RISK_PORTFOLIO = {
    "snapshot": {
        "valuation_date": e2e.TRADE_DATE,
        "portfolio_value": 1_000_000.0,
        "cash": 830_000.0,
        "holdings": [
            {"ticker": "NVDA", "market_value": 20_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
    },
    "target_position": {"target_position_weight": 0.05, "sector": "Technology"},
}


def _buy_proposal(**overrides):
    from tradingagents.agents import schemas

    defaults = {"action": schemas.TraderAction.BUY, "reasoning": "long",
                "entry_price": 100.0, "stop_loss": 90.0, "position_sizing": None}
    defaults.update(overrides)
    return schemas.TraderProposal(**defaults)


def _buy_decision(**overrides):
    from tradingagents.agents import schemas

    defaults = {"rating": schemas.PortfolioRating.BUY, "executive_summary": "buy",
                "investment_thesis": "strong", "price_target": 130.0}
    defaults.update(overrides)
    return schemas.PortfolioDecision(**defaults)


def _graph(tmp_path, monkeypatch, trader_proposal, portfolio_decision, risk_portfolio=None):
    """A real graph whose scripted structured model returns the given proposals."""
    from tradingagents.agents import schemas

    structured = dict(e2e.STRUCTURED)
    structured[schemas.TraderProposal] = trader_proposal
    structured[schemas.PortfolioDecision] = portfolio_decision
    monkeypatch.setattr(e2e, "STRUCTURED", structured, raising=False)
    config = {}
    if risk_portfolio is not None:
        config["risk_portfolio"] = risk_portfolio
    return e2e._graph(tmp_path, monkeypatch, e2e.ScriptedModel(structured=True), **config)


# ---------------------------------------------------------------------------
# A. Programmatic API
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_valid_buy_with_complete_inputs_is_approved(tmp_path, monkeypatch, offline):
    """[SAFETY] A valid BUY with a complete snapshot is APPROVED and actionable."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert state["risk_verdict"] == "APPROVED"
    assert state["decision_status"] == "ACTIONABLE"
    assert signal == "Buy"                       # effective public signal is the model rating
    assert state["model_rating"] == "Buy"        # preserved as evidence


@pytest.mark.unit
def test_missing_stop_loss_is_rejected_and_review(tmp_path, monkeypatch, offline):
    """[SAFETY] INV-A1: a BUY without a stop-loss is REJECTED and REVIEW."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(stop_loss=None), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert state["risk_verdict"] == "REJECTED"
    assert state["decision_status"] == "BLOCKED"
    assert signal == RATING_REVIEW
    assert state["model_rating"] == "Buy"        # original recommendation retained


@pytest.mark.unit
def test_missing_required_information_is_needs_review_and_review(tmp_path, monkeypatch, offline):
    """[SAFETY] Without the structured snapshot the gate fails closed: REVIEW."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=None)           # nothing supplied -> incomplete inputs
    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)

    assert state["risk_verdict"] == "NEEDS_REVIEW"
    assert state["decision_status"] == "PENDING_REVIEW"
    assert signal == RATING_REVIEW
    assert state["model_rating"] == "Buy"


# ---------------------------------------------------------------------------

def _run_real_cli(tmp_path, monkeypatch, trader_proposal, portfolio_decision):
    """Drive the **real** ``cli.run.run_analysis`` with a real graph.

    The graph is built by the real ``TradingAgentsGraph`` constructor (its LLM
    client factory is pointed at the offline scripted model). ``record_decision``
    is NOT patched: the real state log and memory write happen. There is no
    ``risk_portfolio`` CLI flag or environment variable; the default CLI path
    therefore runs without a structured snapshot and must fail closed. Displayed
    output is captured to verify the effective published rating.
    """
    import io

    import cli.run as cli_run
    from cli.models import AnalystType
    from tradingagents.graph import trading_graph as tg

    # Point the graph's LLM factory at the offline scripted model.
    structured = dict(e2e.STRUCTURED)
    from tradingagents.agents import schemas
    structured[schemas.TraderProposal] = trader_proposal
    structured[schemas.PortfolioDecision] = portfolio_decision
    monkeypatch.setattr(e2e, "STRUCTURED", structured, raising=False)
    model = e2e.ScriptedModel(structured=True)
    monkeypatch.setattr(tg, "create_tier_client", lambda config, tier, **k: e2e._Client(model))

    real_build = cli_run._build_run_config

    def build_with_paths(selections, checkpoint):
        # Delegate to the real function, then relocate run artifacts to the test
        # tmp dir. No risk snapshot is injected: the CLI has no such input.
        cfg = real_build(selections, checkpoint)
        cfg["data_cache_dir"] = str(tmp_path / "cache")
        cfg["results_dir"] = str(tmp_path / "results")
        return cfg

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

    captured_out = io.StringIO()
    import rich.console as rich_console
    monkeypatch.setattr(cli_run, "console", rich_console.Console(file=captured_out, width=120))
    monkeypatch.setattr(cli_run, "message_buffer", _Buffer())
    monkeypatch.setattr(cli_run, "create_layout", lambda: None)
    monkeypatch.setattr(cli_run, "update_display", lambda *a, **k: None)
    monkeypatch.setattr(cli_run, "Live", _NullLive)
    monkeypatch.setattr(cli_run, "_build_run_config", build_with_paths)
    monkeypatch.setattr(cli_run, "get_user_selections", lambda flags=None: {
        "ticker": "NVDA", "analysis_date": e2e.TRADE_DATE,
        "analysts": [AnalystType.MARKET], "asset_type": "stock",
        "research_depth": 1, "quick_think_llm": "q", "deep_think_llm": "d",
        "backend_url": None, "llm_provider": "openai", "output_language": "English",
    })
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "N")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    flags = {"ticker": "NVDA", "date": e2e.TRADE_DATE, "analysts": "market",
             "save": False, "show": False, "html": False}
    cli_run.run_analysis(flags=flags)
    return captured_out.getvalue()


def _real_state_log(tmp_path):
    import json
    from pathlib import Path
    logs = sorted(Path(tmp_path / "results").glob("NVDA/TradingAgentsStrategy_logs/*.json"))
    assert logs, "real record_decision did not write a state log"
    return json.loads(logs[-1].read_text())


@pytest.mark.unit
def test_cli_displays_review_and_records_risk_controlled_result(tmp_path, monkeypatch, offline):
    """[SAFETY] The real CLI displays REVIEW for a blocked BUY and records it.

    ``record_decision`` is real: the state log on disk carries the gate verdict.
    The CLI supplies no risk snapshot (no such flag), so even a would-be REJECTED
    BUY is surfaced as REVIEW and persisted as such via the real recording path.
    """
    out = _run_real_cli(tmp_path, monkeypatch, _buy_proposal(stop_loss=None),
                        _buy_decision())
    # The visible post-run notice announces a REVIEW (a decision nobody approved).
    assert "recorded for review" in out.lower()

    entry = _real_state_log(tmp_path)
    assert entry["risk_verdict"] in ("REJECTED", "NEEDS_REVIEW")
    assert entry["final_rating"] == RATING_REVIEW
    assert entry.get("policy_version") == "fr-a1-v1"


@pytest.mark.unit
def test_cli_default_path_without_snapshot_fails_closed(tmp_path, monkeypatch, offline):
    """[SAFETY] The default CLI path (no structured snapshot) fails closed to REVIEW.

    No CLI flag or environment supplies a risk snapshot today, so the default run
    must be NEEDS_REVIEW/REVIEW even for a model that says Buy.
    """
    out = _run_real_cli(tmp_path, monkeypatch, _buy_proposal(), _buy_decision())
    assert "recorded for review" in out.lower()
    entry = _real_state_log(tmp_path)
    assert entry["risk_verdict"] == "NEEDS_REVIEW"
    assert entry["final_rating"] == RATING_REVIEW


@pytest.mark.unit
def test_python_api_config_supplies_risk_portfolio(tmp_path, monkeypatch, offline):
    """[SAFETY] The Python API is the supported path to supply risk_portfolio.

    ``TradingAgentsGraph(config={"risk_portfolio": ...})`` is the approved caller
    path for valid inputs (no CLI flag exists). It yields APPROVED and an
    actionable final rating.
    """
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)
    state, signal = graph.propagate("NVDA", e2e.TRADE_DATE)
    assert state["risk_verdict"] == "APPROVED"
    assert state["decision_status"] == "ACTIONABLE"
    assert state["final_rating"] == "Buy"
    assert signal == "Buy"


# ---------------------------------------------------------------------------
# C. No actionable BUY published before evaluation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_actionable_buy_is_published_before_evaluation(tmp_path, monkeypatch, offline):
    """[SAFETY] Every streamed step carrying a final rating already carries the
    gate's verdict; no intermediate state exposes an unapproved actionable BUY."""
    graph = _graph(tmp_path, monkeypatch, _buy_proposal(stop_loss=None), _buy_decision(),
                   risk_portfolio=RISK_PORTFOLIO)

    seen_final_states = []
    for _messages, chunk in graph.stream_run(
            graph.create_run_state("NVDA", e2e.TRADE_DATE), **graph.propagator.get_graph_args()):
        if chunk and "final_rating" in chunk:
            seen_final_states.append(chunk)

    assert seen_final_states, "expected at least one streamed final decision"
    for chunk in seen_final_states:
        if chunk["final_rating"] == "Buy":
            assert chunk.get("risk_verdict") == "APPROVED"
        else:
            assert chunk["final_rating"] == RATING_REVIEW
