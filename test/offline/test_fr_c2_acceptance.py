"""FR-C2 acceptance tests (TEST-FIRST): one skip log per run, no re-entry, no retry.

These are written against the APPROVED plan (docs/req/fr-c2-plan.md), before the
feature is implemented. Until the production pieces land, the collection/attribute
lookups here will fail for the expected reason (feature not implemented), not
because the tests are wrong.

Contract under test (from the plan):
  * tradingagents.dataflows.vendor_skip.RunSkipState
        - acquire(key) -> ("skipped"|"winner"|"waiter", slot|None)
        - finish(key, slot, skipped: bool)  (winner always calls in finally)
        - log_once(...) responsible for the single skip log
  * router.route_to_vendor(method, *args, state: RunSkipState | None = None, **kwargs)
  * fred.get_api_key(): empty / whitespace-only key counts as unconfigured
  * skip logging is owned by ONE layer (router); FRED does not double-log
  * FRED skipped -> continue to next fallback vendor, never a bare sentinel return

Counts for a run with a missing FRED key and macro_data=fred, N tool calls:
  tool calls = N, router calls = N, data-source entries = 1, HTTP = 0,
  skip logs = 1, sentinels returned = N.

All data/models are simulated; no real credentials, no network.
"""

from __future__ import annotations

import contextvars
import copy
import logging
import re
import threading
import time

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import router
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.vendors import fred


# ---- The approved contract's names are imported INSIDE each test so collection
# succeeds and every case fails for the true reason (feature not implemented),
# rather than a single module-level ImportError hiding the individual results.
def _run_skip_state():
    from tradingagents.dataflows.vendor_skip import RunSkipState
    return RunSkipState()


SKIP_LOG_MARKERS = re.compile(r"skip|not configured|unavailable", re.IGNORECASE)


def _reset_config():
    config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)


@pytest.fixture(autouse=True)
def _clean_config(monkeypatch):
    _reset_config()
    yield
    _reset_config()


def _capture_skip_logs(caplog, level=logging.WARNING):
    """Return the records whose message reads like a skip/unavailable notice."""
    return [r for r in caplog.records if r.levelno >= level and SKIP_LOG_MARKERS.search(r.getMessage())]


def _fred_entry_counter(monkeypatch):
    """Patch fred.get_macro_data to count entries (and simulate the missing key).

    We keep the REAL get_api_key path out of the picture by making the patched
    function raise FredNotConfiguredError, exactly as get_api_key would.
    """
    calls = {"n": 0}

    def _impl(*a, **k):
        calls["n"] += 1
        raise fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)")

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _impl)
    return calls


def _route_macro(state=None):
    if state is None:
        return router.route_to_vendor("get_macro_indicators", "cpi", "2026-01-09", 365)
    return router.route_to_vendor("get_macro_indicators", "cpi", "2026-01-09", 365, state=state)


# ---------------------------------------------------------------------------
# 1. Missing key: exact counts, one log, no HTTP, fallback sentinel returned.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_missing_key_one_log_no_http_sentinel_per_call(monkeypatch, caplog):
    set_config({"data_vendors": {"macro_data": "fred"}})
    entries = _fred_entry_counter(monkeypatch)
    http = {"n": 0}
    monkeypatch.setattr(
        "tradingagents.dataflows.net.requests.get",
        lambda *a, **k: http.__setitem__("n", http["n"] + 1),
    )

    state = _run_skip_state()
    caplog.set_level(logging.WARNING)
    results = [_route_macro(state) for _ in range(5)]

    assert entries["n"] == 1, f"data-source entered {entries['n']} times, expected 1"
    assert http["n"] == 0, "no HTTP must be attempted"
    logs = _capture_skip_logs(caplog)
    assert len(logs) == 1, f"expected exactly one skip log, got {len(logs)}"
    assert all(r.startswith("DATA_UNAVAILABLE") for r in results), results


# ---------------------------------------------------------------------------
# 2. Empty / whitespace key counts as unconfigured (real get_api_key).
# ---------------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   ", "\t\n"], ids=["empty", "spaces", "whitespace"])
def test_blank_key_is_unconfigured(monkeypatch, value):
    monkeypatch.setenv("FRED_API_KEY", value)
    with pytest.raises(fred.FredNotConfiguredError):
        fred.get_api_key()


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   ", "\t\n"], ids=["empty", "spaces", "whitespace"])
def test_real_get_macro_data_blank_key_makes_no_http(monkeypatch, value):
    """Exercise the REAL fred.get_macro_data (not a throwing fake).

    Only the network exit (requests.get) is replaced and counted; the real
    get_api_key / _request path runs. A blank key must raise FredNotConfiguredError
    BEFORE any HTTP is attempted.
    """
    monkeypatch.setenv("FRED_API_KEY", value)
    http = {"n": 0}

    def _no_net(*a, **k):
        http["n"] += 1
        raise AssertionError("network must not be reached with a blank key")

    monkeypatch.setattr("tradingagents.dataflows.net.requests.get", _no_net)

    with pytest.raises(fred.FredNotConfiguredError):
        fred.get_macro_data("cpi", "2026-01-09", 365)
    assert http["n"] == 0, "blank key must not reach the network"


@pytest.mark.unit
def test_real_get_macro_data_with_key_counts_http(monkeypatch):
    """Sanity: with a (fake) key the real path DOES hit the (patched) network.

    Proves the counter is wired to the real function, so the blank-key zero-HTTP
    result above is meaningful, not an artefact of a fake.
    """
    monkeypatch.setenv("FRED_API_KEY", "test-key-not-real")
    http = {"n": 0}

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"seriess": [], "observations": []}

    def _fake_net(*a, **k):
        http["n"] += 1
        return _Resp()

    monkeypatch.setattr("tradingagents.dataflows.net.requests.get", _fake_net)

    out = fred.get_macro_data("cpi", "2026-01-09", 365)
    assert http["n"] >= 1, "real path with a key should reach the network exit"
    assert isinstance(out, str)


# ---------------------------------------------------------------------------
# 3. Repeated calls, same run, different indicators: still 1 data entry, 0 HTTP.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_repeated_calls_across_indicators_enter_source_once(monkeypatch, caplog):
    set_config({"data_vendors": {"macro_data": "fred"}})
    entries = _fred_entry_counter(monkeypatch)
    state = _run_skip_state()
    caplog.set_level(logging.WARNING)

    for indicator in ("cpi", "unemployment", "DGS10"):
        for _ in range(3):
            router.route_to_vendor(
                "get_macro_indicators", indicator, "2026-01-09", 365, state=state
            )

    assert entries["n"] == 1, f"data-source entered {entries['n']} times"
    assert len(_capture_skip_logs(caplog)) == 1


# ---------------------------------------------------------------------------
# 4. Real concurrency (outer Barrier + Event-gated stub, main thread releases).
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_concurrent_first_entry_enters_winner_only(monkeypatch, caplog):
    set_config({"data_vendors": {"macro_data": "fred"}})

    n_threads = 6
    entered = threading.Event()     # winner has entered the stub
    release = threading.Event()     # main thread lets the winner finish
    entry_count = {"n": 0}
    count_lock = threading.Lock()

    def _stub(*a, **k):
        with count_lock:
            entry_count["n"] += 1
            seen = entry_count["n"]
        entered.set()
        # If a second caller wrongly enters, this raises (only one release).
        if seen > 1:
            raise AssertionError("second caller entered the data source")
        release.wait(timeout=5)
        raise fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)")

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _stub)

    state = _run_skip_state()
    barrier = threading.Barrier(n_threads, timeout=5)
    results: list[str] = []
    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def _worker():
        try:
            barrier.wait()
            results.append(_route_macro(state))
        except BaseException as exc:  # noqa: BLE001 - collect, never lose a worker error
            with errors_lock:
                errors.append(exc)

    caplog.set_level(logging.WARNING)
    threads = [threading.Thread(target=_worker, name=f"w{i}") for i in range(n_threads)]
    for t in threads:
        t.start()
    try:
        entered_ok = entered.wait(timeout=5)
        # Give any wrong second entrant a chance to appear before releasing.
        time.sleep(0.2)
    finally:
        # Always release the gate and join, even if the wait assertion below fails.
        release.set()
        for t in threads:
            t.join(timeout=10)

    alive = [t.name for t in threads if t.is_alive()]
    assert not alive, f"worker threads still alive: {alive}"
    assert entered_ok, "winner never entered the stub"
    assert not errors, f"worker errors: {errors!r}"
    assert entry_count["n"] == 1, f"data-source entered {entry_count['n']} times"
    assert len(_capture_skip_logs(caplog)) == 1
    assert len(results) == n_threads and all(r.startswith("DATA_UNAVAILABLE") for r in results)


# ---------------------------------------------------------------------------
# 5. Context propagation: same object under independent copied contexts.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_same_state_under_copied_contexts_logs_once(monkeypatch, caplog):
    set_config({"data_vendors": {"macro_data": "fred"}})
    entries = _fred_entry_counter(monkeypatch)
    state = _run_skip_state()
    caplog.set_level(logging.WARNING)

    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def _one():
        try:
            contextvars.copy_context().run(_route_macro, state)
        except BaseException as exc:  # noqa: BLE001
            with errors_lock:
                errors.append(exc)

    threads = [threading.Thread(target=_one, name=f"c{i}") for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    alive = [t.name for t in threads if t.is_alive()]
    assert not alive, f"worker threads still alive: {alive}"
    assert not errors, f"worker errors: {errors!r}"
    assert entries["n"] == 1
    assert len(_capture_skip_logs(caplog)) == 1


# ---------------------------------------------------------------------------
# 6. Two distinct runs (distinct state objects) are isolated: one log each.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_two_runs_isolated_one_log_each(monkeypatch, caplog):
    set_config({"data_vendors": {"macro_data": "fred"}})
    entries = _fred_entry_counter(monkeypatch)
    caplog.set_level(logging.WARNING)

    states = [_run_skip_state(), _run_skip_state()]
    barrier = threading.Barrier(2, timeout=5)
    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def _run(st):
        try:
            barrier.wait()
            for _ in range(3):
                _route_macro(st)
        except BaseException as exc:  # noqa: BLE001 - collect every worker error
            with errors_lock:
                errors.append(exc)

    threads = [threading.Thread(target=_run, args=(st,), name=f"run{i}") for i, st in enumerate(states)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    alive = [t.name for t in threads if t.is_alive()]
    assert not alive, f"worker threads still alive: {alive}"
    assert not errors, f"worker errors: {errors!r}"
    assert entries["n"] == 2, f"each run should enter once; got {entries['n']}"
    assert len(_capture_skip_logs(caplog)) == 2, "each run logs exactly once"


# ---------------------------------------------------------------------------
# 7. Skip then continue fallback (do NOT bare-return a sentinel).
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_fred_skip_continues_to_next_fallback_vendor(monkeypatch, caplog):
    # Configure FRED then a second mock vendor for the same method.
    set_config({"data_vendors": {"macro_data": "fred,backup"}})

    def _fred_nokey(*a, **k):
        raise fred.FredNotConfiguredError("FRED_API_KEY not set (test stub)")

    backup_calls = {"n": 0}

    def _backup(*a, **k):
        backup_calls["n"] += 1
        return "BACKUP_MACRO_DATA"

    monkeypatch.setitem(
        router.VENDOR_METHODS,
        "get_macro_indicators",
        {"fred": _fred_nokey, "backup": _backup},
    )
    caplog.set_level(logging.WARNING)
    state = _run_skip_state()
    out = _route_macro(state)

    assert out == "BACKUP_MACRO_DATA", out          # fallback actually used
    assert backup_calls["n"] == 1
    assert len(_capture_skip_logs(caplog)) == 1      # FRED skip logged once, no sentinel return


# ---------------------------------------------------------------------------
# 8. Non-config errors are NOT recorded as a skip (network stays a real error).
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_network_error_is_not_marked_as_skip(monkeypatch, caplog):
    from tradingagents.dataflows.errors import VendorUnavailableError

    set_config({"data_vendors": {"macro_data": "fred"}})
    calls = {"n": 0}

    def _net_err(*a, **k):
        calls["n"] += 1
        raise VendorUnavailableError("connection reset")

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _net_err)
    caplog.set_level(logging.WARNING)
    state = _run_skip_state()

    out = _route_macro(state)
    assert out.startswith("DATA_UNAVAILABLE"), out
    # A retry with the same state must call the vendor AGAIN (not skipped).
    _route_macro(state)
    assert calls["n"] == 2, "network errors must not be remembered as skips"


# ---------------------------------------------------------------------------
# 9. Configuration recovery: next run with a key fetches normally.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_next_run_with_key_fetches_normally(monkeypatch, caplog):
    set_config({"data_vendors": {"macro_data": "fred"}})
    caplog.set_level(logging.WARNING)

    # Run 1: missing key -> skip.
    monkeypatch.setenv("FRED_API_KEY", "")
    entries = {"n": 0}

    def _nokey(*a, **k):
        entries["n"] += 1
        raise fred.FredNotConfiguredError("no key")

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _nokey)
    _route_macro(_run_skip_state())
    assert entries["n"] == 1
    assert len(_capture_skip_logs(caplog)) == 1

    # Run 2: key present -> the real function should be consulted (fresh state).
    caplog.clear()
    monkeypatch.setenv("FRED_API_KEY", "test-key-not-real")
    monkeypatch.setitem(
        router.VENDOR_METHODS["get_macro_indicators"], "fred",
        lambda *a, **k: "## FRED: ok\n",
    )
    out = _route_macro(_run_skip_state())
    assert out.startswith("## FRED"), out
    assert not _capture_skip_logs(caplog), "no skip log on a configured, successful run"


# ---------------------------------------------------------------------------
# 10. Waiter TIMEOUT: a waiter whose winner never finishes must NOT enter the
#     data source; it takes the explicit error/fallback path and is NOT recorded
#     as missing credentials.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_waiter_timeout_does_not_enter_data_source_and_is_not_skipped(monkeypatch, caplog):
    set_config({"data_vendors": {"macro_data": "fred"}})
    caplog.set_level(logging.WARNING)
    entries = {"n": 0}

    def _impl(*a, **k):
        entries["n"] += 1
        return "SHOULD_NOT_BE_CALLED"

    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", _impl)

    state = _run_skip_state()
    # Make wait() time out quickly, and force this caller to be a waiter by
    # pre-installing a winner slot that nobody completes.
    monkeypatch.setattr(state, "wait", lambda slot, timeout=30.0: None)
    role, slot = state.acquire("fred:not_configured")
    assert role == "winner"  # pre-claim; the router call below will be a waiter

    out = _route_macro(state)

    assert entries["n"] == 0, f"waiter must not enter the data source; entered {entries['n']} times"
    assert out.startswith("DATA_UNAVAILABLE"), out
    # Timeout must not be recorded as missing credentials.
    assert state.acquire("fred:not_configured")[0] != "skipped", \
        "a timeout must not mark the vendor as skipped"
