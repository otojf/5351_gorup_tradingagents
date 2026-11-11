# Trace Matrix

Every requirement maps to its enforcing component, its test/evidence, and its
runtime monitor. This matrix currently covers **NFR-E1** and its nested
supporting requirements (FR-E1, FR-E2, FR-E3, INV-E1). Rows for other owners'
primaries are appended as their branches merge; their IDs are defined in
`docs/req/requirements-options.yaml`.

Source of truth for fields: `docs/req/requirements.yaml`.

## NFR-E1 — Reproducible fixed-case evaluation (Owner E)

| Requirement | Enforcing component | Test (file::function) | Evidence | Runtime monitor |
|---|---|---|---|---|
| **NFR-E1** reproducible eval, ≤10 min offline, six gates | `eval/` (`runner.py`, `manifest.py`), `.github/workflows/ci.yml` | `tests/test_eval_harness.py::test_suite_runs_three_times_with_stable_rating_reports_and_tokens`; `tests/test_eval_harness.py::test_same_case_twice_is_identical` | `docs/evidence/e1/verification/test-results.txt` | `eval_pass_rate` |
| **FR-E1** golden set 3–5 (ticker,date) + before/after table | `eval/golden.py`, `eval/compare.py` | `tests/test_eval_harness.py::test_golden_set_has_three_distinct_cases`; `tests/test_eval_harness.py::test_compare_covers_all_three_cases_with_a_real_difference` | `docs/evidence/e1/demo/` | `eval_pass_rate` |
| **FR-E2** run manifest (commit/model/prompt/config/data/tokens/latency/degradations/risk/traceability) | `eval/manifest.py` | `tests/test_eval_harness.py::test_run_one_golden_case_returns_rating_and_manifest`; `tests/test_eval_harness.py::test_manifest_unknown_fields_are_null_with_source` | `docs/evidence/e1/verification/test-results.txt` (manifest sample) | `manifest_completeness` |
| **FR-E3** six blocking CI gates | `.github/workflows/ci.yml` | `tests/test_eval_harness.py::test_ci_six_gates` (added in Phase 4) | `docs/evidence/e1/verification/` (bad-PR captures, Phase 4) | `ci_gate_status` |
| **INV-E1** no merge with a failing gate; no secrets | `.github/workflows/ci.yml` + branch protection | `tests/test_eval_harness.py::test_invariant_no_merge_with_failing_gate` (added in Phase 4) | `docs/evidence/e1/verification/` (branch-protection capture) | `gate_failures` |

### Notes on status (as of 2026-11-11)

- FR-E1 is `implemented`: the golden set has 3 distinct cases and the before/after
  compare test exercises **all three** cases (one row each, CSV/MD columns match,
  token delta non-null). The harness is deterministic under the scripted source;
  real-input reproducibility (FR-E4 recording/replay) remains out of scope.
- FR-E2 is `partial`: the manifest exists but degradations/risk verdicts/
  traceability are `null` until owners A/B/D merge.
- FR-E3 / INV-E1 are `partial`: all six gates are wired into CI and pass on
  PR #6 (run 43048019537); branch protection requires the 9 checks plus one
  approving review. A real bad PR (#7) was blocked by gate-3 schema (run
  43048868148). The other five gates' bad-input evidence is local
  (`tests/test_ci_gates.py`), not yet separate live PRs; the secret scan is a
  manual check, not an automated gate.
- Runtime monitors (`eval_pass_rate`, `manifest_completeness`, `ci_gate_status`,
  `gate_failures`) are named here for the trace matrix; they are not yet emitted
  by the harness. The manifest is the current per-run record.
