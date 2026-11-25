# Trace Matrix

Every requirement in `docs/req/requirements.yaml` maps to its enforcing
component, its test/evidence, and a runtime monitor. Rows are grouped by the
five primary requirements; nested supporting entries are listed with their
parent. Deferred candidates that remain only as bare references are listed at
the end with the reason they are not delivered.

Source of truth for fields: `docs/req/requirements.yaml`.

## FR-A1 — Deterministic risk gate (Owner A)

| Requirement | Enforcing component | Test (file::function) | Evidence | Runtime monitor |
|---|---|---|---|---|
| **FR-A1** decision safety | `src/tradingagents/risk_gate/` (`engine.py`, `adapter.py`, `policy.py`) | `test/offline/risk_gate/test_100_invalid_fixtures.py::test_invalid_fixture_is_never_approved`; `test/offline/risk_gate/test_adapter_safety.py::test_approved_hold_keeps_model_rating`; `test/offline/risk_gate/test_decision_boundary.py::test_malformed_risk_portfolio_is_needs_review_not_a_crash` | `docs/evidence/fr-a1/` | `risk_verdict_count` |
| **INV-A1** no approval without stop-loss / cap | `src/tradingagents/risk_gate/engine.py` | `test/offline/risk_gate/test_invariants.py::test_invariant_sweep_never_approves_violations` | `docs/evidence/fr-a1/verification/test-results.txt` | `invariant_violations` |
| **NFR-A1** p95 <= 2 s, zero network | `src/tradingagents/risk_gate/` | `test/offline/risk_gate/test_latency_no_network.py::test_p95_core_evaluation_latency_within_two_seconds`; `test_engine_imports_no_network_or_llm_module` | `docs/evidence/fr-a1/verification/` | `risk_gate_latency_ms` |
| **NFR-A2** auditable evaluations | `src/tradingagents/risk_gate/adapter.py` | `test/offline/risk_gate/test_audit_trail.py::test_every_evaluation_has_a_complete_audit_record` | `docs/evidence/fr-a1/` | `risk_audit_coverage` |

## FR-B1 / FR-B2 — Evidence traceability and citation checking (Owner B)

| Requirement | Enforcing component | Test (file::function) | Evidence | Runtime monitor |
|---|---|---|---|---|
| **FR-B1** structured evidence (partial) | `src/fr_b2/` (delivered part: FR-B2) | `test/offline/fr_b2/test_check_citations.py::test_positive_resolves_to_report_and_snapshot`; `test_negatives_never_count_as_supported` | `docs/evidence/fr-b2/verification.md` | `traceability_coverage` |
| **FR-B2** conclusion citation checker | `src/fr_b2/check_citations.py` | `test/offline/fr_b2/test_check_citations.py` (positive + five negatives); `test/offline/fr_b2/test_review_followups.py::test_registered_evidence_hashes_match` | `docs/evidence/fr-b2/` | `traceability_coverage` |
| **INV-B1** no supported claim without a valid ref | `src/fr_b2/check_citations.py` | `test/offline/fr_b2/test_check_citations.py::test_negatives_never_count_as_supported` | `docs/evidence/fr-b2/verification.md` | `invariant_violations` |

## NFR-C1 — Cost control and FRED skip (Owner C)

| Requirement | Enforcing component | Test (file::function) | Evidence | Runtime monitor |
|---|---|---|---|---|
| **NFR-C1** cost target (partial) | `src/tradingagents/dataflows/` (delivered part: FR-C2) | `test/offline/test_fr_c2_acceptance.py::test_missing_key_one_log_no_http_sentinel_per_call`; `test_two_runs_isolated_one_log_each` | `docs/evidence/fr-c2/implementation-verification.md` | `run_tokens` |
| **FR-C2** skip unconfigured FRED once per run | `src/tradingagents/dataflows/vendor_skip.py`, `router.py` | `test/offline/test_fr_c2_acceptance.py::test_waiter_timeout_does_not_enter_data_source_and_is_not_skipped`; `test_next_run_with_key_fetches_normally` | `docs/evidence/fr-c2/` | `vendor_skip_count` |

## FR-D2 — Visible structured-output degradation (Owner D)

| Requirement | Enforcing component | Test (file::function) | Evidence | Runtime monitor |
|---|---|---|---|---|
| **FR-D2** retry twice, then DEGRADED | `src/tradingagents/agents/structured.py`; `src/tradingagents/agents/state.py`; report writers | `test/offline/test_structured_degradation.py::test_three_failures_degrade`; `test_exactly_three_attempts_bounds_the_cost`; `test_degraded_marker` | `docs/evidence/e1/` (integration) | `degradation_count` |
| **INV-D1** no silent degradation | `src/tradingagents/agents/structured.py` | `test/offline/test_structured_degradation.py::test_invariant_no_silent_degradation` | `docs/evidence/e1/` | `invariant_violations` |

## NFR-E1 — Reproducible offline evaluation and governance (Owner E)

| Requirement | Enforcing component | Test (file::function) | Evidence | Runtime monitor |
|---|---|---|---|---|
| **NFR-E1** reproducible eval, <=10 min offline, six gates | `src/eval/` (`runner.py`, `manifest.py`), `.github/workflows/ci.yml` | `test/offline/test_eval_harness.py::test_suite_runs_three_times_with_stable_rating_reports_and_tokens`; `test_repeats_keep_token_count_within_five_percent`; `test_run_makes_no_network_calls`; `test_offline_run_finishes_under_ten_minutes` | `docs/evidence/e1/verification/test-results.txt` | `eval_pass_rate` |
| **FR-E1** golden set 3-5 + before/after table | `src/eval/golden.py`, `compare.py` | `test/offline/test_eval_harness.py::test_golden_set_has_three_distinct_cases`; `test_compare_covers_all_three_cases_with_a_real_difference` | `docs/evidence/e1/demo/` | `eval_pass_rate` |
| **FR-E2** run manifest | `src/eval/manifest.py`, `manifest_rules.py` | `test/offline/test_eval_harness.py::test_run_one_golden_case_returns_rating_and_manifest`; `test_manifest_prompt_hash_is_real_sha256_and_stable`; `test_prompt_hash_changes_when_prompt_content_changes`; `test_manifest_records_injected_integration_data`; `test_manifest_unknown_fields_are_null_with_source` | `docs/evidence/e1/verification/test-results.txt` | `manifest_completeness` |
| **FR-E3** six blocking CI gates | `.github/workflows/ci.yml`, `scripts/ci/` | `test/offline/test_ci_gates.py` (per-gate negative tests); `test_gate_scripts_importable_and_have_main` | `docs/evidence/e1/verification/`; real bad PR #7 blocked by gate-3 | `ci_gate_status` |
| **INV-E1** no merge with a failing gate; no secrets | `.github/workflows/ci.yml` + branch protection + `scripts/ci/check_secrets.py` | `test/offline/test_ci_gates.py::test_gate3_bad_input_missing_field`; `test_gate2_secret_scan_real_repo_clean` | `docs/evidence/e1/verification/branch-protection.md`; bad PR #7 never merged | `gate_failures` |
| **NFR-GOV-02** branch protection + six gates | GitHub branch protection + `.github/workflows/ci.yml` | `test/offline/test_ci_gates.py::test_gate_scripts_importable_and_have_main` | `docs/evidence/e1/verification/branch-protection.md` | `ci_gate_status` |
| **NFR-SEC-01** no secrets in repo | `scripts/ci/check_secrets.py` (gate 2) | `test/offline/test_ci_gates.py::test_gate2_secret_scan_real_repo_clean` | `docs/evidence/e1/verification/test-results.txt` | `secret_findings` |

## Deferred references (not delivered, kept in the option pool)

The following IDs remain bare references in the registry and are **not** in the
delivered scope. They are tracked in `docs/req/requirements-options.yaml`; no
test or runtime monitor is claimed for them.

| ID | Reason not delivered |
|---|---|
| FR-A2 | Human approval queue; FR-A1 emits `NEEDS_REVIEW` instead. |
| NFR-B1, NFR-B2 | Full structured `EvidenceRef` coverage and evidence lookup latency; FR-B1 is partial, FR-B2 is the delivered checker. |
| FR-C1, FR-C3, NFR-C2 | Token budget/circuit breaker and per-agent ledger; NFR-C1 is partial and only FR-C2 is delivered. |
| FR-D1, FR-D3, NFR-D1 | Full tool-call counting/exit-status propagation and zero-silent-degradation eval metric; FR-D2 is the delivered path. |
