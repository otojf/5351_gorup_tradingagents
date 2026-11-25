# Evaluation Logbook (D2.9, optional)

The accumulated evidence behind the architecture choices. Real captures only;
the current authoritative capture is `docs/evidence/e1/verification/test-results.txt`.

## Entries

### 2026-11-11 — NFR-E1 harness determinism

- Question: is the harness + graph structure deterministic under a fixed scripted
  source?
- Method: run the eval harness (`pytest test/offline/test_eval_harness.py`) and
  repeat a case 3× via `run_suite`.
- Result: ratings/reports/tokens identical across repeats under the scripted
  source; 21 eval tests passed at that point.
- Conclusion: structural determinism proven; real-input reproducibility is NOT
  proven (FR-E4).
- Evidence: `docs/evidence/e1/verification/test-results.txt`.

### 2026-11-11 — six CI gates (local)

- Question: do the six gate scripts behave correctly on good and bad inputs?
- Method: `pytest test/offline/test_ci_gates.py` plus manual gate runs; schema
  gate rejects a registry missing `fit_criterion`; test-approval rejects TODO
  placeholders.
- Result: 37 tests total green locally (21 eval + 16 CI); gate 1 fails by design
  until the approval record is filled; gates 2/3 pass.
- Conclusion: gates function locally; CI wiring is in place.
- Evidence: `docs/evidence/e1/verification/test-results.txt`.

### 2026-11-20 — integrated CI on PR #14

- Question: do the six gates and the clean-install smoke pass together on the
  integrated tree?
- Method: GitHub Actions run on PR #14; local full suite on the integration tip.
- Result: 10 successful jobs (five single gate jobs, four regression matrix jobs,
  clean-install smoke); local 1,789 passed, 6 skipped, 1 deselected, 1 xpassed.
- Conclusion: gates and packaging agree on the integrated tree.
- Evidence: run 44767650957; `docs/evidence/e1/test-approval.md`.

### 2026-11-25 — final main CI and branch protection

- Question: does the submitted `main` still satisfy the required checks after the
  report merge?
- Method: GitHub Actions push run on `b220fff`; `gh api .../branches/main/protection`.
- Result: run 45433613941 succeeded; branch protection requires the nine named
  checks, one approving review, strict status checks, and `enforce_admins`.
- Conclusion: the submission tip is green and protected; the only live bad-PR
  capture remains gate-3 on PR #7.
- Evidence: `docs/evidence/e1/verification/branch-protection.md`;
  `docs/evidence/e1/verification/test-results.txt`.

> Add a new dated entry whenever an architecture choice is validated or revised;
> link the capture.
