# FR-A1 Verification Evidence

`test-results.txt` is the **actual** captured output of the verification commands
run at commit `e716596`. It is not a summary; it contains the real command lines,
stdout/stderr, and exit codes.

## Commands and how to reproduce

Run from the repository root:

```bash
python -m ruff check tradingagents/risk_gate tradingagents/agents tradingagents/graph tests/risk_gate
python -m pytest tests/risk_gate -q
python -m pytest -q --ignore=tests/risk_gate
```

## Last captured results (from `test-results.txt`)

| Step | Result | Exit code |
|---|---|---|
| Ruff | All checks passed | 0 |
| FR-A1 suite (`tests/risk_gate`) | 239 passed, 1 xpassed | 0 |
| Baseline regression (excluding FR-A1) | 1412 passed, 1 skipped, 1 deselected, 24 warnings, 100 subtests passed | 0 |

Notes on the transport, not the substance:

- The single **xpassed** test is `test_trade_scope.py::test_proposed_sell_with_position_data_is_evaluated`,
  a documented non-strict proposal for the pending SELL/HOLD decision (P2). It is
  enabled because the current engine correctly predicts the proposed outcome; it is
  not a failure.
- The single **skipped** baseline test is `tests/test_bedrock_provider.py`
  (`langchain_aws` not installed) — unrelated to FR-A1 and pre-existing.
- The 24 warnings are the baseline suite's normal deprecation/format warnings.

## What these results establish

- The deterministic core, the integration boundary, the safety-edge tests, and the
  audit/durable-destination tests all pass.
- The full baseline behaviour is preserved after the approved fail-closed contract
  migration (runs without `risk_portfolio` surface `REVIEW`).

Do not treat any value here as expected-in-advance: it is transcribed from the run
recorded in `test-results.txt`.
