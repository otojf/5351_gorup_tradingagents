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
| **NFR-E1** reproducible eval, ≤10 min offline, six gates | `eval/` (`runner.py`, `manifest.py`), `.github/workflows/ci.yml` | `tests/test_eval_harness.py::test_suite_runs_three_times_with_stable_rating_reports_and_tokens`; `tests/test_eval_harness.py::test_repeats_keep_token_count_within_five_percent`; `tests/test_eval_harness.py::test_run_makes_no_network_calls`; `tests/test_eval_harness.py::test_offline_run_finishes_under_ten_minutes` | `docs/evidence/e1/verification/test-results.txt` | `eval_pass_rate` |
| **FR-E1** golden set 3–5 (ticker,date) + before/after table | `eval/golden.py`, `eval/compare.py` | `tests/test_eval_harness.py::test_golden_set_has_three_distinct_cases`; `tests/test_eval_harness.py::test_compare_covers_all_three_cases_with_a_real_difference` | `docs/evidence/e1/demo/` | `eval_pass_rate` |
| **FR-E2** run manifest (commit/model/prompt hash/config/data/tokens/latency/degradations/risk/traceability) | `eval/manifest.py`, `eval/manifest_rules.py` | `tests/test_eval_harness.py::test_run_one_golden_case_returns_rating_and_manifest`; `tests/test_eval_harness.py::test_manifest_prompt_hash_is_real_sha256_and_stable`; `tests/test_eval_harness.py::test_prompt_hash_changes_when_prompt_content_changes`; `tests/test_eval_harness.py::test_manifest_records_injected_integration_data`; `tests/test_eval_harness.py::test_manifest_unknown_fields_are_null_with_source` | `docs/evidence/e1/verification/test-results.txt` (manifest sample) | `manifest_completeness` |
| **FR-E3** six blocking CI gates | `.github/workflows/ci.yml`, `scripts/ci/` | Local negative unit tests in `tests/test_ci_gates.py` (`test_gate_scripts_importable_and_have_main` + per-gate `*_bad_input_*` / `*_mocked_fail` cases) | `docs/evidence/e1/verification/` — real bad PR #7 blocked by **gate-3 only**; other five gates have local negative tests only | `ci_gate_status` |
| **INV-E1** no merge with a failing gate; no secrets | `.github/workflows/ci.yml` + branch protection | `tests/test_ci_gates.py::test_gate3_bad_input_missing_field` (a failing gate condition is detected); no unit test can prove GitHub branch protection itself | `docs/evidence/e1/verification/branch-protection.md` (branch-protection capture); bad PR #7 never merged | `gate_failures` |

### Notes on status (as of 2026-11-20, after PR #6 review response)

- FR-E1 is `implemented`: the golden set has 3 distinct cases and the before/after
  compare test exercises **all three** cases (one row each, CSV/MD columns match,
  token delta non-null). The harness is deterministic under the scripted source;
  real-input reproducibility (FR-E4 recording/replay) remains out of scope.
- NFR-E1 metrics now have machine checks: token fluctuation across repeats is
  asserted `<= 5%` (it is 0 under the scripted source); a run is executed with
  `socket.socket.connect`, `socket.create_connection` and `urllib.request.urlopen`
  patched to fail, asserting **0 network calls**; the offline suite's recorded
  latency and measured wall clock are asserted `< 600 s`. Latency is **not**
  asserted to a 5% band: per-call scheduling noise exceeds that and would be
  flaky, so only the 10-minute ceiling is enforced.
- FR-E2 is `partial`: the manifest records a **real** `prompt_hash` (sha256 over
  the prompt-template source) and a separate `prompt_source_id` label.
  `test_prompt_hash_changes_when_prompt_content_changes` proves the hash is
  content-derived: editing one prompt module's bytes in a copied tree changes the
  hash, so it is not a constant or a label. The
  `degradations`/`risk_verdicts`/`traceability` fields are `null` with a reason
  until owners A/B/D wire real producers; the injection interface (field shapes)
  is drafted in `eval/manifest_rules.py` and exercised with fake data by
  `test_manifest_records_injected_integration_data`.
- FR-E3 / INV-E1 are `partial`: all six gates are wired into CI and pass on
  PR #6 (run 43048019537); branch protection requires the 9 checks plus one
  approving review. **The only live bad-PR evidence is gate-3**: real bad PR #7
  was blocked by the schema gate (run 43048868148). The other five gates only
  have **local negative unit tests** (`tests/test_ci_gates.py`) — there is **no
  live bad-PR capture** for them, and none is claimed here. The secret scan is a
  manual check, not an automated gate.
- Runtime monitors (`eval_pass_rate`, `manifest_completeness`, `ci_gate_status`,
  `gate_failures`) are named here for the trace matrix; they are not yet emitted
  by the harness. The manifest is the current per-run record.
