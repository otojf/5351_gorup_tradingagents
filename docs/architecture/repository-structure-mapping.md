# Required Repository Structure — Mapping

The course specification (D8, §5 "Required Repository Structure") names
`src/` (full source) and `test/offline/` + `test/live/`. This repository now uses
that layout **physically** on `main` (merged through PR #13/#14), so the table
below documents the real locations (no longer a mapping away from spec paths).

| Spec path (§5/D8) | Actual path in this repo | Notes |
|---|---|---|
| `src/` (full source) | `src/tradingagents/`, `src/cli/`, `src/eval/`, `src/fr_b2/` | Application source under a `src/` layout; packages keep their import names. Set in `pyproject.toml` (`packages.find where=["src"]`). Module names match architectural elements (analysts/managers/researchers/risk_mgmt/dataflows/graph). |
| `test/offline/` (deterministic tests) | `test/offline/` | Deterministic, offline tests; default `-m "not integration"`. Includes `test/offline/test_eval_harness.py`, `test/offline/risk_gate/`, `test/offline/fr_b2/`. |
| `test/live/` (API-dependent tests) | `test/live/` | Requires external API access; `@pytest.mark.integration`, run only with `-m integration`. Holds `test/live/test_deepseek_reasoning_live.py`. |
| `README.md` | `README.md` | Documents gates (D7) and how to run offline / live / full suite. |
| `AGENTS.md` | `AGENTS.md` | D3 coding-agent entry point. |
| `architecture-blueprint.md` | `architecture-blueprint.md` | D2.1 master constraint document. |
| `Prompt.md` | `Prompt.md` | D9 static startup prompt. |
| `Report.md` | `Report.md` | D6 process report; final version merged through PR #19 (7.5k words, five reflections). |
| `docs/req/requirements.yaml` | `docs/req/requirements.yaml` | D1 registry. |
| `docs/req/req-schema.json` | `docs/req/req-schema.json` | D1 CI schema. |
| `docs/architecture/*` | `docs/architecture/` | `adr/`, `invariants.md`, `trace-matrix.md`, `memory-design.md`, `permission-model.md`, `runtime-policy-catalog.md`, `evaluation-table.md`, `evaluation-logbook.md`, `risk-list.md`, `option-ledger.md`, `repository-structure-mapping.md`. |
| `docs/evidence/*` | `docs/evidence/` | e1 / fr-a1 / fr-b2 / fr-c2 evidence folders. |
| `docs/ai-use-log.yaml` | `docs/ai-use-log.yaml` | D1 AI-use log. |
| `docs/code-governance/*` | `docs/code-governance/` | D3/D4: structural-constraints, verification-constraints, mcp-tool-manifest. |
| `docs/review-memo.md`, `docs/debt-register.md`, `docs/bug-diary.md` | `docs/` | D4 QA records. |
| `.opencode/`, `.agent/` | `.opencode/`, `.agent/` | D3 permissions + rules. |
| `.github/workflows/ci.yml` | `.github/workflows/ci.yml` | D4/D7 six blocking gates. |
| `prompts/prompt_v1.*.yaml` | `prompts/prompt_v1.0.yaml`, `prompts/prompt_v1.1.yaml` | Versioned runtime prompt records restored from the compliance history (PR #13); runtime prompts remain inlined in agent modules. |
| `transcripts/<student-id>-<student-name>.md` | `transcripts/` | D5: annotated transcripts for E1, B2, C2, D2, and A1. D2 covers the FR-D2 reimplementation session (PR #17); A1 covers the FR-A1 decision-safety session (PR #15). All five are present on `main`. |

## Why the earlier "mapping-only" decision changed

- The team chose to physically adopt the D8 layout so reviewers find `src/` and
  `test/offline|live/` exactly where the spec expects them.
- The `src/` layout keeps package import names unchanged (`tradingagents`,
  `cli`, `eval`, `fr_b2`); `pyproject.toml` sets `packages.find where=["src"]`
  and `testpaths = ["test/offline", "test/live"]`.
- Cross-test imports were updated from `tests.*` to `test.offline.*`; a physical
  `test/live/` now isolates the only API-dependent test.
