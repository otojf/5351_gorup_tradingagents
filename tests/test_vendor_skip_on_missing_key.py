"""FR-C2: missing credentials are skipped once per analysis, never sent to HTTP."""

import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from unittest.mock import Mock

import pytest

from tradingagents.dataflows import router
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.vendor_run_state import current_vendor_run, vendor_run_scope
from tradingagents.dataflows.vendors import fred

pytestmark = pytest.mark.unit


def _macro(indicator="cpi"):
    return router.route_to_vendor("get_macro_indicators", indicator, "2026-11-12", 30)


def _skip_events(caplog):
    return [r for r in caplog.records if getattr(r, "event", None) == "vendor_skipped"]


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_vendor_skip_on_missing_key(monkeypatch, caplog, missing):
    if missing is None:
        monkeypatch.delenv("FRED_API_KEY", raising=False)
    else:
        monkeypatch.setenv("FRED_API_KEY", missing)
    set_config({"data_vendors": {"macro_data": "fred"}})
    vendor = Mock(side_effect=AssertionError("unconfigured vendor must not be entered"))
    http = Mock(side_effect=AssertionError("missing credentials must never reach HTTP"))
    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", vendor)
    monkeypatch.setattr(fred, "get_scrubbed", http)
    with caplog.at_level(logging.WARNING), vendor_run_scope() as run:
        outputs = [_macro(ind) for ind in ["cpi"] * 5 + ["unemployment", "10y_treasury"]]
        assert run.vendor_skip_count == 1
    assert all(out.startswith("DATA_UNAVAILABLE") for out in outputs)
    vendor.assert_not_called()
    http.assert_not_called()
    events = _skip_events(caplog)
    assert len(events) == 1
    assert events[0].run_id == run.run_id
    assert events[0].vendor == "fred"
    assert events[0].reason == "missing_credentials"
    assert events[0].vendor_skip_count == 1
    assert len(caplog.records) == 1  # no duplicate optional-category warning
    assert current_vendor_run() is None


def test_next_run_rechecks_credentials_and_normal_calls_are_not_cached(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    vendor = Mock(return_value="MACRO_OK")
    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", vendor)
    with vendor_run_scope() as first:
        assert _macro().startswith("DATA_UNAVAILABLE")
        monkeypatch.setenv("FRED_API_KEY", "synthetic-test-only")
        assert _macro().startswith("DATA_UNAVAILABLE")  # frozen for this run only
    with vendor_run_scope() as second:
        assert _macro() == "MACRO_OK"
        assert _macro("unemployment") == "MACRO_OK"
        assert second.vendor_skip_count == 0
    assert first.run_id != second.run_id
    assert vendor.call_count == 2


def test_same_run_concurrent_calls_log_once(monkeypatch, caplog):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    vendor = Mock(side_effect=AssertionError("vendor should be skipped"))
    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", vendor)
    with caplog.at_level(logging.WARNING), vendor_run_scope() as run:
        contexts = [copy_context() for _ in range(12)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            outputs = list(pool.map(lambda ctx: ctx.run(_macro), contexts))
        assert run.vendor_skip_count == 1
    assert all(x.startswith("DATA_UNAVAILABLE") for x in outputs)
    assert len(_skip_events(caplog)) == 1
    vendor.assert_not_called()


def test_concurrent_runs_do_not_share_skip_state(monkeypatch, caplog):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    def analysis(_):
        with vendor_run_scope() as run:
            assert _macro().startswith("DATA_UNAVAILABLE")
            return run.run_id, run.vendor_skip_count
    with caplog.at_level(logging.WARNING), ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(analysis, range(2)))
    assert len({run_id for run_id, _ in results}) == 2
    assert [count for _, count in results] == [1, 1]
    assert len(_skip_events(caplog)) == 2


def test_other_suppliers_and_explicit_fallback_still_work(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setitem(router.VENDOR_METHODS["get_stock_data"], "yfinance", lambda *a: "PRICES")
    with vendor_run_scope():
        assert _macro().startswith("DATA_UNAVAILABLE")
        assert router.route_to_vendor("get_stock_data", "NVDA", "2026-11-01", "2026-11-12") == "PRICES"
        # The next *configured* supplier still gets a chance; unchosen vendors do not.
        set_config({"data_vendors": {"macro_data": "fred,test_fallback"}})
        monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "test_fallback", lambda *a: "FALLBACK")
        assert _macro() == "FALLBACK"


def test_scope_cleans_up_on_exception():
    with pytest.raises(RuntimeError, match="interrupted"), vendor_run_scope():
        raise RuntimeError("interrupted")
    assert current_vendor_run() is None


def test_nested_scope_restores_outer_state():
    with vendor_run_scope() as outer:
        with vendor_run_scope() as inner:
            assert inner is not outer
        assert current_vendor_run() is outer


def test_configured_vendor_network_failure_is_not_blacklisted(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "synthetic-test-only")
    vendor = Mock(side_effect=TimeoutError("synthetic timeout"))
    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", vendor)
    with vendor_run_scope() as run:
        assert _macro().startswith("DATA_UNAVAILABLE")
        assert _macro().startswith("DATA_UNAVAILABLE")
        assert run.vendor_skip_count == 0
    assert vendor.call_count == 2


def test_not_configured_exception_is_remembered_without_logging_its_contents(monkeypatch, caplog):
    monkeypatch.setenv("FRED_API_KEY", "synthetic-test-only")
    vendor = Mock(side_effect=fred.FredNotConfiguredError("SENSITIVE_ERROR_DO_NOT_LOG"))
    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", vendor)
    with caplog.at_level(logging.WARNING), vendor_run_scope() as run:
        first, second = _macro(), _macro("unemployment")
        assert run.vendor_skip_count == 1
    assert first.startswith("DATA_UNAVAILABLE") and second.startswith("DATA_UNAVAILABLE")
    assert vendor.call_count == 1
    assert len(_skip_events(caplog)) == 1
    assert "SENSITIVE_ERROR_DO_NOT_LOG" not in caplog.text + first + second


def test_core_supplier_keeps_its_original_configuration_error_type(monkeypatch):
    from tradingagents.dataflows.vendors.alpha_vantage.common import AlphaVantageNotConfiguredError

    set_config({"data_vendors": {"core_stock_apis": "alpha_vantage"}})
    supplier = Mock(side_effect=AlphaVantageNotConfiguredError("synthetic missing configuration"))
    monkeypatch.setitem(router.VENDOR_METHODS["get_stock_data"], "alpha_vantage", supplier)
    with vendor_run_scope(), pytest.raises(AlphaVantageNotConfiguredError):
        router.route_to_vendor("get_stock_data", "NVDA", "2026-11-01", "2026-11-12")
