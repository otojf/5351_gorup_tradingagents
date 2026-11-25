# Invariant Register

Every invariant with its statement, source requirement ID, enforcing component,
verification method, and an operational fallback if it is ever violated. A
fallback is a concrete action, not "fix the bug".

Source of truth for statements/fit criteria: `docs/req/requirements.yaml`.
All invariants below are in scope on `main`; none is deferred to a feature
branch.

## INV-A1 — No approval without a stop-loss or above the single-name cap

| Field | Value |
|---|---|
| Statement | A long actionable BUY must carry a stop-loss, must stay within the single-name cap, and must be a genuine increase of the existing position. Missing or unusable inputs must never become `APPROVED`. |
| Source requirement | FR-A1 (nested `INV-A1`, `NFR-A1`, `NFR-A2`) |
| Enforcing component | `src/tradingagents/risk_gate/engine.py` + `adapter.py` at the Portfolio Manager output boundary |
| Verification method | `test/offline/risk_gate/test_invariants.py::test_invariant_sweep_never_approves_violations`; `test/offline/risk_gate/test_100_invalid_fixtures.py::test_invalid_fixture_is_never_approved` (100 distinct invalid fixtures); `test/offline/risk_gate/test_adapter_safety.py` covers malformed portfolios and approved `HOLD`. |
| Operational fallback (on violation) | **Block publication and force REVIEW.** (1) The adapter must not expose an actionable rating: publish `REVIEW`. (2) Write an audit record naming the violated rule ID and the input snapshot. (3) Open an incident note in `docs/evidence/fr-a1/` and notify the FR-A1 owner. (4) Add the failing case to the 100-fixture sweep before re-enabling approval. |

## INV-B1 — No SUPPORTED claim without a valid EvidenceRef

| Field | Value |
|---|---|
| Statement | A claim marked `SUPPORTED` must resolve to a registered source, a readable evidence file, a valid locator, and the expected excerpt. A claim without a valid reference is `UNTRACEABLE` and is excluded from the supported count. |
| Source requirement | FR-B1 (nested `INV-B1`; delivered through FR-B2) |
| Enforcing component | `src/fr_b2/check_citations.py` (offline checker) |
| Verification method | `test/offline/fr_b2/test_check_citations.py::test_negatives_never_count_as_supported`; `test_positive_resolves_to_report_and_snapshot`; `test/offline/fr_b2/test_review_followups.py::test_registered_evidence_hashes_match`. Status is **partial**: the delivered checker validates supplied citations, not a fully structured `EvidenceRef` on every decision field (FR-B1 remains partial in the registry). |
| Operational fallback (on violation) | **Demote the claim, do not count it, and re-run the checker.** (1) Change the claim to `UNTRACEABLE` with a reason. (2) Exclude it from `supported`/coverage totals. (3) Re-run the integrity check against the registered SHA-256 evidence manifest. (4) Record the case in the bug diary and add a regression example before reporting a supported count again. |

## INV-D1 — No silent structured-output degradation

| Field | Value |
|---|---|
| Statement | A structured-output call that fails parsing or validation is attempted once and retried at most twice; a `RETRY` middle state is allowed, but if every attempt fails the result must be marked `DEGRADED` and the affected report section must show a warning. Silent fallback is forbidden. |
| Source requirement | FR-D2 (nested `INV-D1`, `NFR-D1`) |
| Enforcing component | `src/tradingagents/agents/structured.py`; `AgentState.structured_degradations`; report writers in `src/tradingagents/reporting.py` and `report_html.py` |
| Verification method | `test/offline/test_structured_degradation.py::test_invariant_no_silent_degradation`; `test_three_failures_degrade`; `test_degraded_marker`; `test_degraded_section_warning_in_markdown`; `test_degraded_section_warning_in_html`. |
| Operational fallback (on violation) | **Surface the fallback and force REVIEW.** (1) Mark the run `DEGRADED` and add the visible report warning. (2) Record the degradation event with agent and section. (3) If the gate has no structured decision, publish `REVIEW`, not an actionable rating. (4) Add the case to the 20-run forced-failure sweep and notify the FR-D2 owner. |

## INV-E1 — No merge with a failing gate; no secrets

| Field | Value |
|---|---|
| Statement | Any blocking CI gate failure must not be merged; the repository must contain no secret (API key/token). |
| Source requirement | NFR-E1 (nested `INV-E1`, `NFR-GOV-02`, `NFR-SEC-01`) |
| Enforcing component | `.github/workflows/ci.yml` (six blocking gates) + GitHub branch protection + `scripts/ci/check_secrets.py` |
| Verification method | `test/offline/test_ci_gates.py::test_gate_scripts_importable_and_have_main` and the per-gate negative tests; `test/offline/test_ci_gates.py::test_gate2_secret_scan_real_repo_clean`; branch protection requires all nine checks plus one review (see `docs/evidence/e1/verification/branch-protection.md`); the only **live** bad-PR capture is PR #7 blocked by gate-3. No unit test can prove GitHub branch protection itself. |
| Operational fallback (on violation) | **Block / revert, notify, re-run.** (1) Do not merge; if already merged, revert the merge commit on `main` immediately. (2) Open an incident note in `docs/evidence/e1/verification/` naming the gate that was bypassed and the commit. (3) Notify the owning student and the PM owner. (4) Re-run the full gate set on the reverted state; only allow re-merge after 6/6 pass. For a leaked secret: rotate the key first, then purge it from history, then document in the incident note. |
