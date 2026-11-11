# CS5351 Group Project — TradingAgents

## Purpose and architecture

TradingAgents is a multi-agent LLM system that analyses a ticker on a trade date
and produces a five-tier investment rating (`Buy` / `Overweight` / `Hold` /
`Underweight` / `Sell`, or `REVIEW` when no parseable rating exists). Analysts
(market, sentiment, news, fundamentals) run in parallel, feed a Bull/Bear
research debate, then a Trader proposal, a three-way risk debate, and finally the
Portfolio Manager's decision. See `architecture-blueprint.md` for the master
constraint document and `docs/architecture/` for ADRs, invariants, the trace
matrix, and runtime policies.

This project adds, around the baseline (upstream v0.7.1, commit `9fa1196`; team
baseline `46bde74`):

- a **reproducible offline evaluation harness** (NFR-E1: golden set, run
  manifest, before/after comparison) under `eval/`, and
- **six blocking CI gates** (D7) under `scripts/ci/`, wired into
  `.github/workflows/ci.yml`.

## Project layout

| Path | Contents |
|---|---|
| `tradingagents/`, `cli/` | Application source (see `src/README.md` mapping). |
| `tests/` | Deterministic offline tests; live tests via the `integration` marker (see `test/offline/README.md` and `test/live/README.md`). |
| `eval/` | NFR-E1 evaluation harness. |
| `scripts/ci/` | Six blocking-gate scripts. |
| `docs/req/` | Requirements registry + JSON schema. |
| `docs/architecture/` | Blueprint, ADRs, invariants, trace matrix, policies. |
| `docs/code-governance/` | Structural/verification constraints, tool manifest. |
| `docs/evidence/` | Per-feature verification evidence. |
| `docs/ai-use-log.yaml` | AI-use log (gate 6). |
| `prompts/` | Versioned runtime-prompt records. |

## Install and run tests

```bash
pip install -e ".[dev]"

# Offline (default) — deterministic, no network
pytest -q

# Live/API-dependent tests (requires API access; excluded by default)
pytest -m integration

# Full suite including live tests
pytest -m ""

# Lint
ruff check .
```

## GitHub repository

https://github.com/otojf/5351_gorup_tradingagents

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
