"""FR-C2 full-graph checks; reuse the existing offline scripted harness."""

import pytest

from tests import test_graph_end_to_end as harness
from tradingagents.dataflows import router

offline = harness.offline
TRADE_DATE = harness.TRADE_DATE


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["propagate", "debug", "stream"])
def test_missing_fred_key_skips_once_and_full_analysis_continues(
    tmp_path, monkeypatch, offline, caplog, mode,
):
    """FR-C2: ToolNode repeats missing-key calls without retrying the supplier."""
    from unittest.mock import Mock

    from tradingagents.dataflows.vendor_run_state import current_vendor_run
    from tradingagents.dataflows.vendors import fred

    class RepeatedMacroModel(harness.ScriptedModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            result = super()._generate(messages, stop, run_manager, **kwargs)
            message = result.generations[0].message
            macro = next((c for c in message.tool_calls if c["name"] == "get_macro_indicators"), None)
            if macro is not None:
                message.tool_calls.extend(
                    {**macro, "id": f"macro_repeat_{i}", "args": {**macro["args"], "indicator": ind}}
                    for i, ind in enumerate(("cpi", "unemployment"))
                )
            return result

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    supplier = Mock(side_effect=AssertionError("missing-key FRED must be skipped before entry"))
    http = Mock(side_effect=AssertionError("no FRED HTTP is permitted"))
    monkeypatch.setitem(router.VENDOR_METHODS["get_macro_indicators"], "fred", supplier)
    monkeypatch.setattr(fred, "get_scrubbed", http)
    graph = harness._graph(tmp_path, monkeypatch, RepeatedMacroModel(structured=True), debug=mode == "debug")
    if mode == "stream":
        final_state = {}
        stream = graph.stream_run(graph.create_run_state("NVDA", TRADE_DATE), **graph.propagator.get_graph_args())
        for _, state in stream:
            assert current_vendor_run() is None  # stream context never leaks to its caller
            if state:
                final_state.update(state)
    else:
        final_state, _ = graph.propagate("NVDA", TRADE_DATE)
    assert final_state["final_rating"] in {"Buy", "Overweight", "Hold", "Underweight", "Sell", "REVIEW"}
    assert final_state["final_trade_decision"]
    assert final_state["news_report"]
    supplier.assert_not_called()
    http.assert_not_called()
    events = [r for r in caplog.records if getattr(r, "event", None) == "vendor_skipped"]
    assert len(events) == 1
    assert events[0].vendor_skip_count == 1
    assert current_vendor_run() is None
