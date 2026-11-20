# Verification Constraints (D4)

The verification rules the verification agent applies, and the QA records the
team maintains.

## 1. Coverage rules

1. **Every fit criterion has at least one test.** Each `fit_criterion` in
   `docs/req/requirements.yaml` (including nested supporting requirements) is
   exercised by at least one test.
2. **Every invariant has a negative test.** For each entry in
   `docs/architecture/invariants.md` there is at least one test that *fails when
   the invariant is violated* (at least one negative test per feature).
3. **Every test references its requirement/invariant.** Test names and/or a
   top-of-test comment name the requirement ID or invariant it verifies.
4. **Zero regressions.** Every new round runs all previous rounds' test suites;
   `scripts/ci/check_regression.py` blocks on any failure.

## 2. Three-tier verification

- **Structural** — imports, module boundaries, permissions, architectural fitness
  functions (e.g. `tests/test_layering.py`, the structural constraints above).
- **Regression** — all prior suites pass (`pytest -q`, gate 5).
- **Behavioral** — quality thresholds: faithfulness/relevance where applicable,
  zero safety escapes (gate 4 replays the fixed golden set).

## 3. The six blocking gates (D7)

| Gate | Script | Rule enforced |
|---|---|---|
| 1 test-approval | `check_test_approval.py` | tests approved before implementation (`docs/evidence/e1/test-approval.md`) |
| 2 static analysis | `check_static_analysis.py` | ruff + pip check + compileall (type-check/contract/security/permission NOT covered — stated) |
| 3 schema | `check_schema.py` | registry validates against `req-schema.json` |
| 4 semantic eval | `check_semantic_eval.py` | fixed golden set yields expected output |
| 5 regression | `check_regression.py` | full prior suite passes |
| 6 AI-use log | `check_ai_use_log.py` | code/prompt change updates `docs/ai-use-log.yaml` |

Wired in `.github/workflows/ci.yml`; branch protection requires nine checks + one
approving review (names in
`docs/evidence/e1/verification/branch-protection.md`).

## 4. Negative-test requirement (per feature)

Each feature adds at least one test that passes only because the feature's
safety behavior is correct, and fails if it regresses. For the eval harness, the
negative tests include: schema gate rejects a registry missing `fit_criterion`;
AI-use-log gate rejects an uncovered code change; test-approval gate rejects a
record with TODO placeholders; `run_suite` rejects a single context for multiple
cases.

## 5. QA records

- `docs/review-memo.md` — one memo per PR (spec/architecture/code/test quality,
  operational metadata, verdict APPROVE / CHANGES REQUIRED / REJECT).
- `docs/debt-register.md` — technical debt across AI-era categories.
- `docs/bug-diary.md` — one entry per significant bug.
