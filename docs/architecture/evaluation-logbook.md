# Evaluation Logbook (D2.9, optional)

The accumulated evidence behind the architecture choices. Real captures only; the
current authoritative capture is `docs/evidence/e1/verification/test-results.txt`.

## Entries

### 2026-11-11 — NFR-E1 harness determinism

- Question: is the harness + graph structure deterministic under a fixed scripted
  source?
- Method: run the eval harness (`pytest tests/test_eval_harness.py`) and repeat a
  case 3× via `run_suite`.
- Result: ratings/reports/tokens identical across repeats under the scripted
  source; 21 eval tests passed at that point.
- Conclusion: structural determinism proven; real-input reproducibility is NOT
  proven (FR-E4).
- Evidence: `docs/evidence/e1/verification/test-results.txt`.

### 2026-11-11 — six CI gates (local)

- Question: do the six gate scripts behave correctly on good and bad inputs?
- Method: `pytest tests/test_ci_gates.py` (16 tests) + manual gate runs; schema
  gate rejects a registry missing `fit_criterion`; test-approval rejects TODO
  placeholders.
- Result: 37 tests total green locally (21 eval + 16 CI); gate 1 fails by design
  until the approval record is filled; gate 2/3 pass.
- Conclusion: gates function locally; CI wiring is in place; CI run pending.
- Evidence: `docs/evidence/e1/verification/test-results.txt`.

> Add a new dated entry whenever an architecture choice is validated or revised;
> link the capture.
