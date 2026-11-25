# Technical Debt Register (D4)

Technical debt tracked across the AI-era categories. Each item states the debt,
its category, impact, and a re-visit trigger. Entries are real known gaps, not
placeholders. Reviewed 2026-11-25.

| ID | Category | Debt | Impact | Re-visit trigger |
|---|---|---|---|---|
| DEBT-01 | evaluation debt | The eval harness proves structural determinism under a scripted source, not real-input reproducibility. | Ratings cannot be claimed reproducible on live data. | FR-E4 (recorded replay) approved. |
| DEBT-02 | guardrail debt | Gate 2 type-checks only the safety-critical modules; the upstream baseline and a full API-compatibility suite are not covered. | A type or API regression in an untouched baseline module can pass CI. | A baseline module becomes safety-relevant, or mypy/pyright is adopted repo-wide. |
| DEBT-03 | evaluation debt | Manifest `degradations`, `risk_verdicts` and `traceability` are `null` with a reason until all producers are wired. | Manifest is incomplete on those fields. | A/B/D producer changes or a manifest schema change. |
| DEBT-04 | human/cognitive debt | Test-approval gate is a human record; the script only checks it is filled, not that approval truly preceded coding. | Gate can be satisfied superficially. | Automated test-first proof adopted. |
| DEBT-05 | hidden dependencies | `yaml` was imported via a transitive dependency before being declared; now in dev extras. | Previously flaky CI. | Resolved; watch for new transitive-only imports. |
| DEBT-06 | prompt rot | Runtime prompts in `prompts/` are versioned; no automated drift check against `docs/architecture/adr/` yet. | Prompt/architecture drift. | Drift check added. |
| DEBT-07 | untouchable code | Most of the upstream baseline has no type coverage and few targeted tests; it is effectively read-only except for narrowly approved changes. | Agents cannot safely refactor baseline modules; changes require an ADR and extra review. | A baseline module needs a feature change; DEBT-02 is retired. |
| DEBT-08 | agent-induced bloat | Compliance docs are extensive; risk of stale content if not co-evolved with code. | Docs drift from reality. | A doc/code mismatch is found in review. |
| DEBT-09 | hallucinated dependencies | Early trace-matrix/registry drafts referenced two nonexistent test names; they were replaced with real tests and the schema gate now runs in CI. | An AI-generated reference can look authoritative while pointing at nothing. | Any new test/evidence reference in the registry or trace matrix. |
| DEBT-10 | evaluation debt | The semantic-eval gate proves the fixed scripted golden set, not real-input semantic quality thresholds. | A model/prompt quality regression outside the scripted set is not blocked. | Real-input replay (FR-E4) or a quality-threshold evaluator is added. |
