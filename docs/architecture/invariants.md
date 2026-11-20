# Invariant Register

Every invariant with its statement, source requirement ID, enforcing component,
verification method, and an operational fallback if it is ever violated. A
fallback is a concrete action, not "fix the bug".

Source of truth for statements/fit criteria: `docs/req/requirements.yaml`.

## INV-E1 — No merge with a failing gate; no secrets

| Field | Value |
|---|---|
| Statement | Any blocking CI gate failure must not be merged; the repository must contain no secret (API key/token). |
| Source requirement | NFR-E1 (nested `INV-E1`) |
| Type | invariant (zero tolerance) |
| Enforcing component | `.github/workflows/ci.yml` (six blocking gates) + GitHub branch protection |
| Verification method | `tests/test_ci_gates.py::test_gate3_bad_input_missing_field` (a failing gate condition is detected locally); branch protection requires all nine checks plus one review (see `docs/evidence/e1/verification/branch-protection.md`); the only **live** bad-PR capture is PR #7 blocked by gate-3 (see `test-results.txt`); secret scan is a manual check. No unit test can prove GitHub branch protection itself. |
| Operational fallback (on violation) | **Block / revert, notify, re-run.** (1) Do not merge; if already merged, revert the merge commit on `main` immediately. (2) Open an incident note in `docs/evidence/e1/verification/` naming the gate that was bypassed and the commit. (3) Notify the owning student and the PM owner. (4) Re-run the full gate set on the reverted state; only allow re-merge after 6/6 pass. For a leaked secret: rotate the key first, then purge it from history, then document in the incident note. |

## Other invariants (reference only — owned by other branches)

These are defined in `docs/req/requirements-options.yaml` and will be entered
here with their own fallbacks when their branches merge; they are **not**
implemented on this branch:

- `INV-A1` — no APPROVED decision without a stop-loss / under the single-name cap.
- `INV-B1` — no SUPPORTED claim without a valid EvidenceRef.
- `INV-D1` — no silent structured-output degradation.
