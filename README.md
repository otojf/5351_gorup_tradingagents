# CS5351 Group Project — TradingAgents

这个仓库目前包含：

| 路径 | 内容 |
|---|---|
| `src/tradingagents/`、`src/cli/`、`src/eval/`、`src/fr_b2/` | 应用源码（D8 `src/` 布局；上游 v0.7.1，commit `9fa1196`） |
| `test/offline/` | 确定性离线测试（默认 `-m "not integration"`） |
| `test/live/` | 需外部 API 的集成测试（`@pytest.mark.integration`，显式 `-m integration` 才跑） |
| `docs/req/requirements.yaml` | 最终 5 条主需求 |
| `docs/req/requirements-options.yaml` | 35 条候选需求，供组员挑选 |

安装：`pip install -e ".[dev]"`

## 运行测试

```bash
# 离线（默认，确定性、无网络）
python -m pytest                     # 等价于 pytest test/offline test/live -m "not integration"
# 仅 live（需真实 API key）
python -m pytest test/live -m integration
# 全部
python -m pytest test/offline test/live
```

## Blocking gates (D7)

Six blocking gates are implemented under `scripts/ci/` and wired into
`.github/workflows/ci.yml`. PR #6 runs all nine required checks; branch
protection (9 checks + one approving review) is configured on `main`.

| # | Gate | Script / command | What it checks | Known gaps (stated, not faked) |
|---|---|---|---|---|
| 1 | test-approval | `scripts/ci/check_test_approval.py` | `docs/evidence/e1/test-approval.md` has approver, date, test scope (no TODO placeholders) | Human gate; script only checks the record exists and is filled, not that approval truly preceded coding |
| 2 | static analysis | `scripts/ci/check_static_analysis.py` | `ruff check .` + `pip check` + `compileall` | **No** type-check (mypy/pyright), contract/API-surface, dedicated security scan, or permission checks |
| 3 | schema | `scripts/ci/check_schema.py` | `requirements.yaml` validates against `req-schema.json` | Structural only; does not judge semantic quality |
| 4 | semantic eval | `scripts/ci/check_semantic_eval.py` | Runs `test/offline/test_eval_harness.py` (fixed golden set) | Deterministic under scripted source; not real-input semantic quality (FR-E4) |
| 5 | regression | `scripts/ci/check_regression.py` | `pytest -q` (full default suite) | — |
| 6 | AI-use log | `scripts/ci/check_ai_use_log.py` | code/prompt change has a matching `docs/ai-use-log.yaml` entry | Presence/coverage only; cannot verify an entry is true |

Gate 1 currently **fails by design** until the team fills `approved_by` in
`docs/evidence/e1/test-approval.md`. Gate scripts' own tests live in
`test/offline/test_ci_gates.py`.

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

This repo now uses the course's D8 layout physically: `src/` holds the
application packages (`tradingagents`, `cli`, `eval`, `fr_b2`) and `test/` holds
`offline/` (deterministic) and `live/` (API-dependent) tests. See
`docs/architecture/repository-structure-mapping.md` for the path-by-path mapping.

## 功能开发分支

| 需求 | 分支 | 入口 |
|---|---|---|
| FR-B2 报告结论引用检查 | `feat/fr-b2-conclusion` | [`src/fr_b2/README.md`](src/fr_b2/README.md) |
