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
| `README.md` | `README.md` | (To be expanded for D7 gates + §4 content in later work.) |
| `AGENTS.md` | *(pending)* | D3 governance file, not yet created. |
| `architecture-blueprint.md` | *(pending)* | D2.1 master constraint document. |
| `Prompt.md` | *(pending)* | D9 static startup prompt. |
| `Report.md` | *(pending)* | D6 process report. |
| `docs/req/requirements.yaml` | `docs/req/requirements.yaml` | D1 registry. |
| `docs/req/req-schema.json` | `docs/req/req-schema.json` | D1 schema (added Phase 1). |
| `docs/architecture/*` | `docs/architecture/` | `trace-matrix.md`, `invariants.md`, `repository-structure-mapping.md`, and `adr/001-eval-harness.md` added (Phase 2); architecture-blueprint and remaining artifacts pending. |
| `docs/evidence/*` | `docs/evidence/` | `docs/evidence/e1/` added (Phase 2, mirrors `docs/evidence/fr-a1/`). |
| `docs/ai-use-log.yaml` | `docs/ai-use-log.yaml` | D1 AI-use log (added Phase 2). |
| `docs/code-governance/*` | *(pending)* | D3/D4 files. |
| `docs/review-memo.md`, `docs/debt-register.md`, `docs/bug-diary.md` | *(pending)* | D4 QA records. |
| `.opencode/`, `.agent/` | *(pending)* | D3 permission/rules files. |
| `.github/workflows/ci.yml` | `.github/workflows/ci.yml` | D4/D7 gates (six gates wired in Phase 4). |
| `prompts/prompt_v1.*.yaml` | *(pending)* | Versioned runtime prompts. |
| `transcripts/<student-id>-<student-name>.md` | `transcripts/opencode-nfr-e1-annotated.md` | D5; rename + add remaining transcripts pending. |

## Why no physical migration now

- The baseline is an upstream-derived package named `tradingagents`; renaming its
  import root to `src` would break every import and the packaging entry point,
  and is out of scope for NFR-E1.
- The `integration` marker already separates deterministic from live tests; a
  physical `test/offline` + `test/live` split adds no behavioural guarantee.
- Reviewers can use this table to locate every specified artifact. A physical
  migration remains a team/PM decision, recorded here for transparency.
