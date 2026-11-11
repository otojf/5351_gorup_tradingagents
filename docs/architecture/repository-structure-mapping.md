# Required Repository Structure — Mapping

The course specification (D8, §5 "Required Repository Structure") names
directories (`src/`, `test/offline/`, `test/live/`) that differ from this
repository's existing layout. The team decided **not** to physically migrate;
this document is the required structural mapping so reviewers can trace every
specified path to its real location.

| Spec path (§5/D8) | Actual path in this repo | Notes |
|---|---|---|
| `src/` (full source) | `tradingagents/` + `cli/` | All application source. `tradingagents/` holds the framework; `cli/` holds the CLI. Module names match architectural elements (analysts/managers/researchers/risk_mgmt/dataflows/graph). |
| `test/offline/` (deterministic tests) | `tests/` | The existing suite is offline/deterministic by default (`addopts = -m "not integration"`, tests monkeypatch vendors and LLMs). Includes `tests/test_eval_harness.py`. |
| `test/live/` (API-dependent tests) | tests marked `integration` within `tests/` | No physical split. Live tests are the subset requiring API access, selected via the `integration` marker (excluded by default). A physical `tests/live/` split is deferred; the marker is the functional equivalent. |
| `README.md` | `README.md` | D7 gates + §4 content. |
| `AGENTS.md` | `AGENTS.md` | D3 governance file. |
| `architecture-blueprint.md` | `architecture-blueprint.md` | D2.1 master constraint document. |
| `Prompt.md` | `Prompt.md` | D9 static startup prompt. |
| `Report.md` | `Report.md` | D6 process report (skeleton; team fills it). |
| `docs/req/requirements.yaml` | `docs/req/requirements.yaml` | D1 registry. |
| `docs/req/req-schema.json` | `docs/req/req-schema.json` | D1 schema. |
| `docs/architecture/*` | `docs/architecture/` | ADR (`adr/001-eval-harness.md`), `invariants.md`, `trace-matrix.md`, `memory-design.md`, `option-ledger.md`, `permission-model.md`, `evaluation-logbook.md`, `risk-list.md`, `evaluation-table.md`, `runtime-policy-catalog.md`, `repository-structure-mapping.md`. |
| `docs/evidence/*` | `docs/evidence/` | `docs/evidence/e1/` (mirrors `fr-a1/`). |
| `docs/ai-use-log.yaml` | `docs/ai-use-log.yaml` | D1 AI-use log. |
| `docs/code-governance/*` | `docs/code-governance/` | `structural-constraints.md`, `verification-constraints.md`, `mcp-tool-manifest.md`. |
| `docs/review-memo.md`, `docs/debt-register.md`, `docs/bug-diary.md` | `docs/` | D4 QA records (review-memo template + debt/bug registers). |
| `.opencode/`, `.agent/` | `.opencode/`, `.agent/` | `permissions.jsonc`, `rules.md`; `.agent/rules.md` (covenant). |
| `.github/workflows/ci.yml` | `.github/workflows/ci.yml` | D4/D7 six gates. |
| `prompts/prompt_v1.*.yaml` | `prompts/prompt_v1.0.yaml`, `prompts/prompt_v1.1.yaml` | Versioned runtime-prompt records (production prompts live in agent modules). |
| `transcripts/<student-id>-<student-name>.md` | `transcripts/60572233-HUANG-SIYING.md`; `transcripts/60572233-HUANG-SIYING-continuation.md` | D5; main E1 transcript + continuation; the other four member transcripts are still pending. |

## Why no physical migration now

- The baseline is an upstream-derived package named `tradingagents`; renaming its
  import root to `src` would break every import and the packaging entry point,
  and is out of scope for NFR-E1.
- The `integration` marker already separates deterministic from live tests; a
  physical `test/offline` + `test/live` split adds no behavioural guarantee.
- Reviewers can use this table to locate every specified artifact. A physical
  migration remains a team/PM decision, recorded here for transparency.
