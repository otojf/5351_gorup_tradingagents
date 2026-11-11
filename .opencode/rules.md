# .opencode/rules.md — Always-On Behavioral Rules (D3)

> Human-only file. Changes require an architecture decision.

These rules apply to every session, always, regardless of task.

## Read and plan before acting

1. Read `AGENTS.md`, then `Prompt.md`, then `architecture-blueprint.md`, and the
   docs in the order listed in `AGENTS.md` §2.
2. For non-trivial changes, produce a plan (traceability, interface contract,
   scope boundaries, testing strategy, steps) and **stop for human approval**.
   Do not run unattended to completion.

## Respect the baseline and boundaries

3. Extend `tradingagents/`, `cli/`, `tests/`, `eval/`; never replace them.
4. Data only through `tradingagents/dataflows/router.py`; models only through
   `tradingagents/llm_clients`. Do not call vendors or providers inline.
5. State keys live in `tradingagents/agents/state.py`; adding is additive, never
   repurpose a key.
6. Model output is advisory; deterministic code decides safety-relevant outcomes.

## Human-only and frozen

7. Do not edit `AGENTS.md`, `Prompt.md`, `.opencode/rules.md`, `.agent/rules.md`,
   or `architecture-blueprint.md` without an architecture decision.
8. Never read or write `.env*`, secrets, or credentials. Never commit secrets.

## Tests and verification

9. Do not weaken or delete a test to pass a gate. Fix the code.
10. Every new feature adds at least one negative test; every test references the
    requirement/invariant it verifies.
11. Run `pytest -q`, `ruff check .`, and the `scripts/ci/` gates before reporting;
    report failures honestly, including uncovered checks.

## Governance

12. Every code/prompt change updates `docs/ai-use-log.yaml`.
13. Safety-critical path changes require an ADR and human review.
14. Do not configure branch protection, push, or commit unless explicitly asked.
