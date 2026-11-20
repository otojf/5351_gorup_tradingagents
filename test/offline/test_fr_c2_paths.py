"""FR-C2 acceptance tests for the three run entry points (TEST-FIRST).

Covers: normal ``propagate``, ``debug=True`` (internal stream_run), direct
``stream_run`` (the CLI path), and two concurrent runs on ONE graph instance.

Contract under test (from docs/req/fr-c2-plan.md): every entry path creates ONE
run-scoped RunSkipState; with a missing FRED key the macro data source is entered
once, no HTTP is attempted, exactly one skip log is written, and the graph still
completes — even when the model issues MULTIPLE macro tool requests in one run
(including several in the same turn).

Written before implementation: until the feature lands these fail for the
expected "not implemented" reason, NOT because the assertions are wrong.

All data/models are simulated; no real credentials, no network.
"""

from __future__ import annotations

import logging
import re
import threading

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from test.offline.test_graph_end_to_end import (
    TEXT,
    ScriptedModel,
    _graph,
    offline,  # noqa: F401  (fixture reused in this module)
)
from tradingagents.dataflows import router

# Imported inside tests so collection succeeds and each case fails for the true
# reason (feature not implemented), not a single module-level ImportError.

SKIP_LOG_MARKERS = re.compile(r"skip|not configured|unavailable", re.IGNORECASE)


def _macro_skip_count(caplog):
    out = []
    for r in caplog.records:
        if r.levelno < logging.WARNING:
            continue
        msg = r.getMessage().lower()
        if SKIP_LOG_MARKERS.search(msg) and ("macro" in msg or "fred" in msg):
            out.append(r)
    return out


def _force_macro_unconfigured(monkeypatch):
    """Make FRED macro raise the not-configured error, counting entries."""
    from tradingagents.dataflows.vendors import fred
    entries = {"n": 0}

    def _nokey(*a, **k):
        entries["n"] += 1
        raise fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)")

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _nokey)
    return entries


def _count_macro_http(monkeypatch):
    """Count real HTTP exits WITHOUT touching the network (fail if reached)."""
    http = {"n": 0}

    def _no_net(*a, **k):
        http["n"] += 1
        raise AssertionError("HTTP must not be attempted for an unconfigured vendor")

    monkeypatch.setattr("tradingagents.dataflows.net.requests.get", _no_net)
    return http


class MacroHeavyModel(ScriptedModel):
    """Like ScriptedModel, but the macro tool is requested several times.

    On the first tool-bound turn it emits THREE concurrent get_macro_indicators
    calls (different indicators) in ONE AIMessage (same turn), and on the next
    turn it emits two more, so a single analysis makes >1 macro tool request.
    All other bound tools are called once, as ScriptedModel does.
    """

    macro_calls_issued: list = []  # note: shared mutable default is intentional per-instance copy

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: D401
        from langchain_core.messages import ToolMessage

        self._count()
        if not self.tools:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=TEXT))])

        tool_names = {t.name for t in self.tools}
        has_macro = "get_macro_indicators" in tool_names

        # After any tool result, answer with the report text (as ScriptedModel).
        if isinstance(messages[-1], ToolMessage):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=TEXT))])

        # First tool turn: several macro calls at once + each other tool once.
        if has_macro:
            calls = []
            for i, ind in enumerate(("cpi", "unemployment", "10y-treasury")):
                calls.append({
                    "name": "get_macro_indicators",
                    "id": f"macro_{i}",
                    "args": {"indicator": ind, "curr_date": "2026-01-09", "look_back_days": 365},
                })
            for t in self.tools:
                if t.name == "get_macro_indicators":
                    continue
                props = t.tool_call_schema.model_json_schema()["properties"]
                calls.append({
                    "name": t.name,
                    "id": f"call_{t.name}",
                    "args": {k: v for k, v in {
                        "symbol": "NVDA", "ticker": "NVDA", "curr_date": "2026-01-09",
                        "start_date": "2026-01-02", "end_date": "2026-01-09",
                        "indicator": "rsi", "topic": "Fed rate cut", "freq": "quarterly",
                    }.items() if k in props},
                })
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=calls))])

        # Non-macro analyst: call every bound tool once (ScriptedModel behavior).
        calls = []
        for t in self.tools:
            props = t.tool_call_schema.model_json_schema()["properties"]
            calls.append({
                "name": t.name,
                "id": f"call_{t.name}",
                "args": {k: v for k, v in {
                    "symbol": "NVDA", "ticker": "NVDA", "curr_date": "2026-01-09",
                    "start_date": "2026-01-02", "end_date": "2026-01-09",
                    "indicator": "rsi", "topic": "Fed rate cut", "freq": "quarterly",
                }.items() if k in props},
            })
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=calls))])


def _tool_request_counter(monkeypatch):
    """Count MACRO TOOL REQUESTS at the router entry (where the tool calls it).

    This counts calls to ``route_to_vendor("get_macro_indicators", ...)`` — i.e.
    tool requests reaching the router — NOT data-source entries. Data-source
    entries are counted separately by the vendor stub passed to
    ``_install_fred_stub``. The two counters are independent on purpose.
    """
    requests = {"n": 0}
    req_lock = threading.Lock()
    real = router.route_to_vendor

    def _counted(method, *a, **k):
        if method == "get_macro_indicators":
            with req_lock:
                requests["n"] += 1
        return real(method, *a, **k)

    monkeypatch.setattr(router, "route_to_vendor", _counted)
    # tools.py imported route_to_vendor by name; patch that binding too so the
    # entry-point count reflects what the tool actually calls.
    monkeypatch.setattr("tradingagents.agents.tools.route_to_vendor", _counted)
    return requests


def _install_fred_stub(monkeypatch, exc_factory):
    """Install a FRED vendor stub that counts DATA-SOURCE ENTRIES and raises."""
    entries = {"n": 0}

    def _impl(*a, **k):
        entries["n"] += 1
        raise exc_factory()

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _impl)
    return entries


# ---------------------------------------------------------------------------
# 1. Multi-request paths: >1 macro tool requests, data source entered 1x, HTTP 0,
#    one log, graph completes. Covers propagate / debug / direct stream_run.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_propagate_multi_macro_requests_skip_once(tmp_path, monkeypatch, offline, caplog):  # noqa: F811
    from tradingagents.dataflows.vendors import fred
    requests = _tool_request_counter(monkeypatch)
    entries = _install_fred_stub(monkeypatch, lambda: fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)"))
    http = _count_macro_http(monkeypatch)
    caplog.set_level(logging.WARNING)
    graph = _graph(tmp_path, monkeypatch, MacroHeavyModel())

    state, signal = graph.propagate("NVDA", "2026-01-09")

    # FR-C2 verifies the graph completes with one FRED entry, zero HTTP and
    # one skip log. With the FR-A1 risk gate integrated and no risk_portfolio
    # supplied, the effective rating is REVIEW (fail-closed), so this test
    # asserts the run reached a valid rating rather than a specific one.
    assert signal in {"Overweight", "REVIEW"}
    assert state["final_trade_decision"].strip()
    assert requests["n"] > 1, f"model should issue multiple macro requests; got {requests['n']}"
    assert entries["n"] == 1, f"data source entered {entries['n']} times, expected 1"
    assert http["n"] == 0, "no HTTP for an unconfigured vendor"
    assert len(_macro_skip_count(caplog)) == 1, "one skip log per run"


@pytest.mark.unit
def test_debug_multi_macro_requests_skip_once(tmp_path, monkeypatch, offline, caplog):  # noqa: F811
    from tradingagents.dataflows.vendors import fred
    requests = _tool_request_counter(monkeypatch)
    entries = _install_fred_stub(monkeypatch, lambda: fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)"))
    http = _count_macro_http(monkeypatch)
    caplog.set_level(logging.WARNING)
    graph = _graph(tmp_path, monkeypatch, MacroHeavyModel(), debug=True)

    state, signal = graph.propagate("NVDA", "2026-01-09")

    # Same as above: FR-A1 makes the effective rating REVIEW without a
    # risk_portfolio; assert a valid rating, not a specific one.
    assert signal in {"Overweight", "REVIEW"}
    assert requests["n"] > 1, f"debug path macro requests={requests['n']}"
    assert entries["n"] == 1, f"debug path entered FRED {entries['n']} times (must not reset)"
    assert http["n"] == 0
    assert len(_macro_skip_count(caplog)) == 1


@pytest.mark.unit
def test_direct_stream_run_multi_macro_requests_skip_once(tmp_path, monkeypatch, offline, caplog):  # noqa: F811
    from tradingagents.dataflows.vendors import fred
    requests = _tool_request_counter(monkeypatch)
    entries = _install_fred_stub(monkeypatch, lambda: fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)"))
    http = _count_macro_http(monkeypatch)
    caplog.set_level(logging.WARNING)
    graph = _graph(tmp_path, monkeypatch, MacroHeavyModel())

    init = graph.create_run_state("NVDA", "2026-01-09")
    for _messages, _chunk in graph.stream_run(init, **graph.propagator.get_graph_args()):
        pass

    assert requests["n"] > 1, f"stream_run macro requests={requests['n']}"
    assert entries["n"] == 1, f"stream_run entered FRED {entries['n']} times"
    assert http["n"] == 0
    assert len(_macro_skip_count(caplog)) == 1


@pytest.mark.unit
def test_direct_stream_run_config_isolation_english_caller_french_graph(
        tmp_path, monkeypatch, offline, caplog):  # noqa: F811
    """The graph uses French; the caller stays English between and after steps."""
    from tradingagents.dataflows.config import get_config, set_config
    from tradingagents.dataflows.vendors import fred

    requests = _tool_request_counter(monkeypatch)
    entries = _install_fred_stub(monkeypatch, lambda: fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)"))
    http = _count_macro_http(monkeypatch)
    caplog.set_level(logging.WARNING)

    # Caller config = English; graph config = French. NB: constructing the graph
    # calls set_config(graph_config) on the process config, so set English AFTER
    # construction to model a caller whose own config differs from the graph's.
    graph = _graph(tmp_path, monkeypatch, MacroHeavyModel(), output_language="French")
    set_config({"output_language": "English"})

    # Record the language the macro tool sees INSIDE the graph (English would be a leak).
    seen_in_graph: list[str] = []
    real_impl = router.VENDOR_METHODS["get_macro_indicators"]["fred"]

    def _spy(*a, **k):
        seen_in_graph.append(get_config()["output_language"])
        return real_impl(*a, **k)

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _spy)

    assert get_config()["output_language"] == "English"  # before the run
    init = graph.create_run_state("NVDA", "2026-01-09")
    between: list[str] = []
    for _messages, _chunk in graph.stream_run(init, **graph.propagator.get_graph_args()):
        between.append(get_config()["output_language"])
    after = get_config()["output_language"]

    assert seen_in_graph, "macro tool never ran inside the graph"
    assert set(seen_in_graph) == {"French"}, f"graph should see French, saw {set(seen_in_graph)}"
    assert between and set(between) == {"English"}, f"caller polluted between steps: {set(between)}"
    assert after == "English", "caller config must be English after the run"
    # Counts still hold on this path.
    assert requests["n"] > 1
    assert entries["n"] == 1
    assert http["n"] == 0
    assert len(_macro_skip_count(caplog)) == 1


# ---------------------------------------------------------------------------
# 2. Same-graph concurrent runs: capture every worker error, join all threads,
#    and release the gate in finally even if an assertion fails first.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_same_graph_instance_concurrent_runs_are_isolated(tmp_path, monkeypatch, offline, caplog):  # noqa: F811
    """Two analyses on ONE TradingAgentsGraph, concurrent, each macro-skipped once.

    State must be a per-run local object (not on self): each run enters the data
    source once (total 2) and logs one skip (total 2).
    """
    from tradingagents.dataflows.vendors import fred
    # Tool requests counted at the router entry; data-source entries counted by
    # a thread-safe stub. They are deliberately separate counters.
    requests = _tool_request_counter(monkeypatch)
    entries = {"n": 0}
    entry_lock = threading.Lock()

    def _nokey(*a, **k):
        with entry_lock:
            entries["n"] += 1
        raise fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)")

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _nokey)
    http = _count_macro_http(monkeypatch)
    caplog.set_level(logging.WARNING)
    graph = _graph(tmp_path, monkeypatch, MacroHeavyModel())

    gate = threading.Event()      # start gate, released in finally
    errors: list[BaseException] = []
    errors_lock = threading.Lock()
    started = threading.Barrier(2, timeout=10)

    def _run(ticker):
        try:
            started.wait()
            gate.wait(timeout=10)
            graph.propagate(ticker, "2026-01-09")
        except BaseException as exc:  # noqa: BLE001 - collect, never lose a worker error
            with errors_lock:
                errors.append(exc)

    threads = [threading.Thread(target=_run, args=(t,), name=f"run-{t}") for t in ("NVDA", "AMD")]
    for t in threads:
        t.start()
    try:
        gate.set()
    finally:
        # Always join and release, even if the gate/assert path fails.
        for t in threads:
            t.join(timeout=60)
    # Every worker thread must have finished; never leave threads running.
    alive = [t.name for t in threads if t.is_alive()]
    assert not alive, f"worker threads still alive: {alive}"
    assert not errors, f"worker errors: {errors!r}"

    assert http["n"] == 0
    # Tool requests are counted at the router entry: two runs, each with several
    # macro calls, so the total exceeds a single run's requests.
    assert requests["n"] > 2, f"tool requests across both runs: {requests['n']}"
    assert entries["n"] == 2, f"each run enters FRED once; got {entries['n']}"
    assert len(_macro_skip_count(caplog)) == 2, "each run logs one skip (isolated)"


# ---------------------------------------------------------------------------
# Reusing the SAME args/config dict for two stream_run calls must NOT reuse the
# run state: run 1 (missing key) skips; run 2 (key restored) calls normally. The
# caller's original config dict must be left unmodified.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_same_config_two_stream_runs_are_independent(tmp_path, monkeypatch, offline, caplog):  # noqa: F811
    import copy as _copy

    from tradingagents.dataflows.vendors import fred

    requests = _tool_request_counter(monkeypatch)
    caplog.set_level(logging.WARNING)
    graph = _graph(tmp_path, monkeypatch, MacroHeavyModel())

    # Run 1: FRED missing key -> skip.
    entries1 = {"n": 0}

    def _nokey(*a, **k):
        entries1["n"] += 1
        raise fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)")

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _nokey)

    # Build ONE args/config dict and reuse the SAME object for both runs (the
    # reported bug path: a caller that holds one config dict and starts a run
    # from it twice).
    args = graph.propagator.get_graph_args()
    config_snapshot = _copy.deepcopy(args.get("config", {}))

    init1 = graph.create_run_state("NVDA", "2026-01-09")
    for _m, _c in graph.stream_run(init1, **args):
        pass
    assert entries1["n"] == 1, f"run 1 should enter once; got {entries1['n']}"
    log1 = len(_macro_skip_count(caplog))
    assert log1 == 1, "run 1 logs one skip"

    # The caller's original config must not have been mutated with fr_skip_state.
    assert "fr_skip_state" not in (args.get("config", {}).get("configurable", {}) or {}), \
        "stream_run must not mutate the caller's config"
    assert args.get("config", {}) == config_snapshot, "caller's config dict must be unchanged"

    # Run 2: restore a mock key -> FRED must be called (same args/config reused).
    caplog.clear()
    calls2 = {"n": 0}

    def _ok(*a, **k):
        calls2["n"] += 1
        return "## FRED: ok\n"

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _ok)

    init2 = graph.create_run_state("NVDA", "2026-01-09")
    for _m, _c in graph.stream_run(init2, **args):
        pass
    assert calls2["n"] >= 1, "run 2 with a restored key must call FRED normally"
    assert len(_macro_skip_count(caplog)) == 0, "run 2 must not log a skip"
    # Run 2's macro tool requests reached the router (counted at the entry).
    assert requests["n"] > 0, f"tool requests across both runs: {requests['n']}"
    # The reused args dict is still not polluted.
    assert "fr_skip_state" not in (args.get("config", {}).get("configurable", {}) or {})
    assert args.get("config", {}) == config_snapshot
