# CS5351 Group Project — TradingAgents

这个仓库目前包含：

| 路径 | 内容 |
|---|---|
| `tradingagents/`、`cli/`、`tests/` | 原始 TradingAgents demo（上游 v0.7.1，commit `9fa1196`） |
| `docs/req/requirements.yaml` | 最终 5 条主需求 |
| `docs/req/requirements-options.yaml` | 35 条候选需求，供组员挑选 |

安装：`pip install -e ".[dev]"`

## Blocking gates (D7)

Six blocking gates are implemented under `scripts/ci/` and wired into
`.github/workflows/ci.yml`. PR #6 runs all nine required checks; branch
protection (9 checks + one approving review) is configured on `main`.

| # | Gate | Script / command | What it checks | Known gaps (stated, not faked) |
|---|---|---|---|---|
| 1 | test-approval | `scripts/ci/check_test_approval.py` | `docs/evidence/e1/test-approval.md` has approver, date, test scope (no TODO placeholders) | Human gate; script only checks the record exists and is filled, not that approval truly preceded coding |
| 2 | static analysis | `scripts/ci/check_static_analysis.py` | `ruff check .` + `pip check` + `compileall` | **No** type-check (mypy/pyright), contract/API-surface, dedicated security scan, or permission checks |
| 3 | schema | `scripts/ci/check_schema.py` | `requirements.yaml` validates against `req-schema.json` | Structural only; does not judge semantic quality |
| 4 | semantic eval | `scripts/ci/check_semantic_eval.py` | Runs `tests/test_eval_harness.py` (fixed golden set) | Deterministic under scripted source; not real-input semantic quality (FR-E4) |
| 5 | regression | `scripts/ci/check_regression.py` | `pytest -q` (full default suite) | — |
| 6 | AI-use log | `scripts/ci/check_ai_use_log.py` | code/prompt change has a matching `docs/ai-use-log.yaml` entry | Presence/coverage only; cannot verify an entry is true |

Gate 1 currently **fails by design** until the team fills `approved_by` in
`docs/evidence/e1/test-approval.md`. Gate scripts' own tests live in
`tests/test_ci_gates.py`.

### CI triggers and required checks

The six gates are wired into `.github/workflows/ci.yml`:

- `push` to `main` / release tags and every `pull_request` run gates 2–5 and the
  `smoke-install` job.
- Gates 1 (`gate-1-test-approval`) and 6 (`gate-6-ai-use-log`) run **only on
  `pull_request`** — they guard a change, not a push.
- `gate-5-regression` keeps the Python 3.11–3.14 matrix (4 checks; the
  `America/New_York` tz is merged into the 3.12 run, not a fifth check).

Branch protection requires these checks (9 total: 5 single jobs + 4
matrix-expanded gate‑5 checks) and one approving review. It is configured on
`main`; the exact names and the `gh api` command are in
`docs/evidence/e1/verification/branch-protection.md`.

## Required-structure mapping

See `docs/architecture/repository-structure-mapping.md` for how the course's
`src/` and `test/offline|live/` map to this repo's `tradingagents/`, `cli/`, and
`tests/`.
