"""Slice 1 of the eval harness: golden set, offline runner, manifest.

These tests prove the harness and the graph structure are deterministic under
scripted data and a scripted model. They do NOT claim real-input reproducibility.
"""

import copy
import json

import pytest

from tradingagents.dataflows import router
from tradingagents.default_config import DEFAULT_CONFIG


def _config(tmp_path):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(tmp_path / "results"),
        data_cache_dir=str(tmp_path / "cache"),
        memory_log_path=str(tmp_path / "log.md"),
    )
    return cfg


@pytest.mark.unit
def test_scripted_source_activates_and_restores(tmp_path):
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    before = router.VENDOR_METHODS["get_stock_data"]["yfinance"]
    ctx = EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource())

    with ctx.activate():
        during = router.VENDOR_METHODS["get_stock_data"]["yfinance"]
        assert during is not before

    after = router.VENDOR_METHODS["get_stock_data"]["yfinance"]
    assert after is before


@pytest.mark.unit
def test_run_one_golden_case_returns_rating_and_manifest(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    case = GOLDEN_SET[0]
    ctx = EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource())
    result = run_case(case, ctx, _config(tmp_path))

    assert result.rating == case.expected_rating
    m = result.manifest
    for key in ("case_id", "ticker", "trade_date", "rating", "model", "config_hash",
                "data_snapshot", "prompt_snapshot", "tool_calls_total", "output_paths"):
        assert key in m, key


@pytest.mark.unit
def test_manifest_tool_counts_from_stream(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    ctx = EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource())
    result = run_case(GOLDEN_SET[0], ctx, _config(tmp_path))

    ok = sum(1 for e in result.tool_events if e["status"] == "ok")
    requested = sum(1 for e in result.tool_events if e["status"] == "requested")

    # The executed count is the finished ToolMessages only, and it must match the
    # callback handler's on_tool_start count (tokens.tool_calls).
    assert result.manifest["tool_calls_total"] == ok
    assert result.manifest["tool_calls_total"] == result.manifest["tokens"]["tool_calls"]
    # The request events (one per AIMessage tool call, carrying args) are counted
    # separately so they are not double-counted against execution.
    assert result.manifest["tool_call_requests_total"] == requested
    assert result.manifest["tool_calls_total"] > 0
    assert requested == ok


@pytest.mark.unit
def test_manifest_unknown_fields_are_null_with_source(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    ctx = EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource())
    result = run_case(GOLDEN_SET[0], ctx, _config(tmp_path))

    m = result.manifest
    for key in ("degradations", "risk_verdicts", "traceability"):
        assert m[key] is None, key
        assert m["unavailable_sources"][key], key


@pytest.mark.unit
def test_output_path_recorded_and_exists(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    ctx = EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource())
    result = run_case(GOLDEN_SET[0], ctx, _config(tmp_path))

    from pathlib import Path

    md = result.manifest["output_paths"]["complete_report_md"]
    assert Path(md).exists()


@pytest.mark.unit
def test_run_id_scopes_the_output_directory(tmp_path):
    from pathlib import Path

    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    case = GOLDEN_SET[0]
    cfg = _config(tmp_path)
    first = run_case(case, EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()), cfg)
    second = run_case(case, EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()), cfg)

    assert first.manifest["run_id"] != second.manifest["run_id"]
    d1 = Path(first.manifest["output_paths"]["report_dir"])
    d2 = Path(second.manifest["output_paths"]["report_dir"])
    assert d1 != d2
    assert d1.name == case.case_id and d2.name == case.case_id
    assert d1.parent.name == first.manifest["run_id"]
    assert d1.exists() and d2.exists()


@pytest.mark.unit
def test_state_log_is_written_and_recorded(tmp_path):
    from pathlib import Path

    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    result = run_case(
        GOLDEN_SET[0], EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()),
        _config(tmp_path),
    )

    state_log = Path(result.manifest["output_paths"]["state_log"])
    assert state_log.exists()


@pytest.mark.unit
def test_manifest_records_token_usage(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    llm = ScriptedLLMSource()
    result = run_case(
        GOLDEN_SET[0], EvalContext(source=ScriptedSource(), llm=llm),
        _config(tmp_path),
    )

    tokens = result.manifest["tokens"]
    assert tokens is not None
    assert set(tokens) >= {"in", "out", "llm_calls"}
    assert tokens["llm_calls"] > 0
    assert tokens["in"] > 0 and tokens["out"] > 0
    # The handler must count each model call exactly once.
    assert tokens["llm_calls"] == len(llm.chat_model("quick").calls)


@pytest.mark.unit
def test_source_protocols_declare_activate_and_use_their_data_methods():
    from eval.sources import LLMSource, ScriptedSource, Source

    # The protocol must declare activate(), or EvalContext is calling something
    # the contract never promised.
    assert hasattr(Source, "activate")
    assert hasattr(LLMSource, "activate")

    # vendor_responses()/ohlcv_frame() must feed activate(), not sit unused:
    # the stubbed vendor and the OHLCV frame come from those methods.
    src = ScriptedSource()
    responses = src.vendor_responses()
    assert responses, "vendor_responses() must return the stub map activate() installs"
    assert src.ohlcv_frame() is not None


@pytest.mark.unit
def test_suite_runs_three_times_with_stable_rating_reports_and_tokens(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    results = run_suite(
        [GOLDEN_SET[0]],
        EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()),
        _config(tmp_path),
        runs=3,
    )

    assert len(results) == 3
    assert {r.rating for r in results} == {GOLDEN_SET[0].expected_rating}
    for key in ("market_report", "sentiment_report", "news_report", "fundamentals_report"):
        assert len({r.final_state[key] for r in results}) == 1, key
    assert len({json.dumps(r.manifest["tokens"], sort_keys=True) for r in results}) == 1
    # Latency is recorded but not asserted to a 5% band: the scripted model's
    # wall-clock noise is too large for that.
    for r in results:
        assert r.manifest["latency_s"] >= 0


@pytest.mark.unit
def test_suite_isolates_memory_log_per_run(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    results = run_suite(
        [GOLDEN_SET[0]],
        EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()),
        _config(tmp_path),
        runs=2,
    )

    # Each run reads its own log: a shared log would feed run 1's decision into
    # run 2, so the two inputs would differ.
    assert len({r.manifest["run_id"] for r in results}) == 2
    assert len({r.manifest["output_paths"]["memory_log"] for r in results}) == 2


@pytest.mark.unit
def test_suite_isolates_state_log_per_run(tmp_path):
    from pathlib import Path

    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    results = run_suite(
        [GOLDEN_SET[0]],
        EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()),
        _config(tmp_path),
        runs=3,
    )

    # A shared results_dir would let the three runs overwrite one state log,
    # so the manifest would record the same path three times.
    paths = [r.manifest["output_paths"]["state_log"] for r in results]
    assert len(set(paths)) == 3
    assert all(Path(p).exists() for p in paths)


@pytest.mark.unit
def test_suite_fresh_llm_source_per_run(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    llm = ScriptedLLMSource()
    results = run_suite(
        [GOLDEN_SET[0]],
        EvalContext(source=ScriptedSource(), llm=llm),
        _config(tmp_path),
        runs=3,
    )

    per_run = {r.manifest["tokens"]["llm_calls"] for r in results}
    assert len(per_run) == 1
    (one,) = per_run
    assert one > 0
    # Each run's model state starts fresh: the shared model holds one run's
    # calls, not three runs'. Otherwise a "fail on call N" stub would fire in a
    # later run.
    assert len(llm.chat_model("quick").calls) == one


@pytest.mark.unit
def test_activate_resets_model_call_history():
    from eval.sources import ScriptedLLMSource

    llm = ScriptedLLMSource()
    model = llm.chat_model("quick")
    model.calls.append(1)
    model.calls.append(1)

    with llm.activate():
        assert model.calls == [], "activate() must reset the scripted model's call history"

    llm2 = ScriptedLLMSource()
    with llm2.activate():
        pass
    with llm2.activate():
        # A second activation also starts clean.
        assert llm2.chat_model("quick").calls == []


@pytest.mark.unit
def test_same_case_twice_is_identical(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_case
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    case = GOLDEN_SET[0]
    # Each run gets its own memory log: a shared log would feed the first run's
    # decision into the second run's Portfolio Manager, so the two inputs would
    # differ and the test would not be comparing like with like.
    first = run_case(
        case,
        EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()),
        _config(tmp_path / "run1"),
    )
    second = run_case(
        case,
        EvalContext(source=ScriptedSource(), llm=ScriptedLLMSource()),
        _config(tmp_path / "run2"),
    )

    assert first.rating == second.rating
    for key in ("market_report", "sentiment_report", "news_report", "fundamentals_report"):
        assert first.final_state[key] == second.final_state[key], key


# ---------------------------------------------------------------------------
# Slice 3: multi-case golden set, per-case fixtures, before/after compare
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_golden_set_has_three_distinct_cases():
    from eval.golden import GOLDEN_SET

    assert len(GOLDEN_SET) >= 3
    pairs = {(c.ticker, c.trade_date) for c in GOLDEN_SET}
    assert len(pairs) == len(GOLDEN_SET)


@pytest.mark.unit
def test_scripted_source_follows_the_case_ticker_and_date():
    from eval.golden import GOLDEN_SET
    from eval.sources import ScriptedLLMSource, ScriptedSource

    case = GOLDEN_SET[0]
    src = ScriptedSource(case.ticker, case.trade_date)
    frame = src.ohlcv_frame()()
    assert str(frame["Date"].iloc[-1].date()) == case.trade_date

    llm = ScriptedLLMSource(case.ticker, case.trade_date)
    assert hasattr(llm.chat_model("quick"), "last_tool_args")


@pytest.mark.unit
def test_run_suite_feeds_each_case_ticker_into_tool_calls(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    def factory(case):
        return EvalContext(
            source=ScriptedSource(case.ticker, case.trade_date),
            llm=ScriptedLLMSource(case.ticker, case.trade_date),
        )

    results = run_suite(GOLDEN_SET, factory, _config(tmp_path), runs=1)

    assert len(results) == len(GOLDEN_SET)
    by_case = {r.case.case_id: r for r in results}
    for case in GOLDEN_SET:
        r = by_case[case.case_id]
        assert r.final_state["company_of_interest"] == case.ticker
        # Every tool call for this case carried the case's own ticker/date in
        # its *args* -- recorded from the graph's AIMessages, so this proves the
        # graph fed the case's instrument to the tools, not just the fixture.
        requested = [e for e in r.manifest["tool_calls"] if e.get("status") == "requested"]
        assert requested, case.case_id
        for event in requested:
            args = event["args"]
            tickers = {args.get(k) for k in ("symbol", "ticker") if k in args}
            if tickers:
                assert tickers == {case.ticker}, (case.case_id, args)
            if "curr_date" in args:
                assert args["curr_date"] == case.trade_date, (case.case_id, args)


@pytest.mark.unit
def test_run_suite_single_case_accepts_instance_or_factory(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    case = GOLDEN_SET[0]

    # A single case may take a plain EvalContext instance.
    instance = EvalContext(
        source=ScriptedSource(case.ticker, case.trade_date),
        llm=ScriptedLLMSource(case.ticker, case.trade_date),
    )
    by_instance = run_suite([case], instance, _config(tmp_path / "inst"), runs=1)

    # ...or a factory.
    def factory(c):
        return EvalContext(
            source=ScriptedSource(c.ticker, c.trade_date),
            llm=ScriptedLLMSource(c.ticker, c.trade_date),
        )

    by_factory = run_suite([case], factory, _config(tmp_path / "fact"), runs=1)

    for results in (by_instance, by_factory):
        assert len(results) == 1
        assert results[0].rating == case.expected_rating
        assert results[0].final_state["company_of_interest"] == case.ticker


@pytest.mark.unit
def test_run_suite_multiple_cases_rejects_single_context(tmp_path):
    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    first = GOLDEN_SET[0]
    instance = EvalContext(
        source=ScriptedSource(first.ticker, first.trade_date),
        llm=ScriptedLLMSource(first.ticker, first.trade_date),
    )

    # A single context would reuse one case's fixtures for every case: rejected.
    with pytest.raises(ValueError, match="factory"):
        run_suite(list(GOLDEN_SET), instance, _config(tmp_path), runs=1)


@pytest.mark.unit
def test_compare_covers_all_three_cases_with_a_real_difference(tmp_path):
    import csv
    import dataclasses
    from pathlib import Path

    from eval.compare import compare
    from eval.golden import GOLDEN_SET
    from eval.runner import run_suite
    from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource

    four = ("market", "social", "news", "fundamentals")
    three = ("market", "news", "fundamentals")

    def case_factory_with(analysts):
        def make(c):
            return dataclasses.replace(c, analysts=analysts)
        return make

    def ctx_factory(c):
        return EvalContext(
            source=ScriptedSource(c.ticker, c.trade_date),
            llm=ScriptedLLMSource(c.ticker, c.trade_date),
        )

    # All three golden cases on both sides; before has the sentiment analyst,
    # after drops it, so every case's token count differs.
    before_cases = [case_factory_with(four)(c) for c in GOLDEN_SET]
    after_cases = [case_factory_with(three)(c) for c in GOLDEN_SET]

    before = run_suite(before_cases, ctx_factory, _config(tmp_path / "before"), runs=1)
    after = run_suite(after_cases, ctx_factory, _config(tmp_path / "after"), runs=1)

    out = compare(before, after, tmp_path / "compare")
    csv_path = Path(out["csv"])
    md_path = Path(out["md"])
    assert csv_path.exists() and md_path.exists()

    rows = out["rows"]
    # One row per case, every case present.
    assert len(rows) == len(GOLDEN_SET)
    assert {row["case_id"] for row in rows} == {c.case_id for c in GOLDEN_SET}

    # Every row shows a real difference and a computed delta.
    for row in rows:
        assert row["before_tokens"] != row["after_tokens"], row
        assert row["token_delta_pct"] is not None, row

    # CSV and MD carry the same columns.
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    md_header = [
        line for line in md_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("| case_id")
    ][0]
    md_cols = [c.strip() for c in md_header.strip("|").split("|")]
    assert md_cols == header
