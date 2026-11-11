# Technical Debt Register (D4)

Technical debt tracked across the AI-era categories. Each item states the debt,
its category, impact, and a re-visit trigger. Entries are real known gaps, not
placeholders.

| ID | Category | Debt | Impact | Re-visit trigger |
|---|---|---|---|---|
| DEBT-01 | evaluation debt | The eval harness proves structural determinism under a scripted source, not real-input reproducibility. | Ratings cannot be claimed reproducible on live data. | FR-E4 (recorded replay) approved. |
| DEBT-02 | guardrail debt | Gate 2 static analysis lacks type-check, contract, API-surface, security, and permission checks. | Regressions those checks would catch can pass CI. | mypy/pyright or a security scanner adopted. |
| DEBT-03 | evaluation debt | Manifest `degradations`, `risk_verdicts`, `traceability` are `null` until owners A/B/D merge. | Manifest is incomplete on those fields. | A/B/D branches merge. |
| DEBT-04 | human/cognitive debt | Test-approval gate is a human record; the script only checks it is filled, not that approval truly preceded coding. | Gate can be satisfied superficially. | Automated test-first proof adopted. |
| DEBT-05 | hidden dependencies | `yaml` was imported via a transitive dependency before being declared; now in dev extras. | Previously flaky CI. | (resolved; watch for new transitive-only imports) |
| DEBT-06 | prompt rot | Runtime prompts in `prompts/` are versioned; no automated drift check against `docs/architecture/adr/` yet. | Prompt/architecture drift. | Drift check added (see `prompts/`). |
| DEBT-07 | structural debt | `src/` and `test/offline|live/` are not physically migrated (mapped instead). | Spec paths differ from actual paths. | Team/PM decides to migrate. |
| DEBT-08 | agent-induced bloat | Compliance docs are extensive; risk of stale content if not co-evolved with code. | Docs drift from reality. | A doc/code mismatch is found in review. |

> TODO (team): append new debt as it is discovered; each item gets an owner and
> date when triaged.
