# AGENTS.md — Coding-Agent Governance (D3)

This is the single entry point the AI coding agent reads. It declares the build
target, the reading order for architecture artifacts, the code baseline, what is
readable/modifiable/frozen, the module organization, the integration contracts
between modules, and the verification requirements the generated code must
satisfy.

Project: CS5351 Agentic Software Engineering Project — TradingAgents.
Upstream baseline: TradingAgents v0.7.1 (commit `9fa1196`), team baseline
`46bde74`. Repository root = this file's directory.

> Human-only files (do not let the agent edit without an architecture decision):
> `AGENTS.md`, `Prompt.md`, `.opencode/rules.md`, `.agent/rules.md`,
> `architecture-blueprint.md`. See `.opencode/permissions.jsonc`.

## 1. Build target

- Package: `tradingagents` (Python ≥3.11). CLI entry: `tradingagents` →
  `cli.main:app`.
- Install: `pip install -e ".[dev]"`.
- Test: `pytest -q` (offline, `-m "not integration"` by default).
- Lint: `ruff check .` (strict select in `pyproject.toml`).
- The NFR-E1 eval harness lives in `eval/`; the six CI gates live in
  `scripts/ci/` and run in `.github/workflows/ci.yml`.

## 2. Reading order (before writing code)

1. This file (`AGENTS.md`).
2. `Prompt.md` — the static launch prompt (plan-first, stop for human approval).
3. `architecture-blueprint.md` — the master constraint document (D2.1).
4. `docs/architecture/adr/` — architecture decisions (start with
   `001-eval-harness.md`).
5. `docs/architecture/invariants.md` — non-negotiable rules.
6. `docs/architecture/trace-matrix.md` — requirement → component → test → monitor.
7. `docs/architecture/runtime-policy-catalog.md` — degraded/failure behavior.
8. `docs/req/requirements.yaml` (+ `req-schema.json`) — the requirements registry.
9. `.opencode/rules.md` and `.agent/rules.md` — always-on behavioral rules.
10. `docs/code-governance/structural-constraints.md` and
    `verification-constraints.md`.

## 3. Code baseline and module organization

- Baseline: the existing `tradingagents/`, `cli/`, `tests/`, `eval/` code.
  **Extend the existing baseline; never replace it.**
- Each architectural element maps to exactly one module:
  - `tradingagents/agents/analysts/` — the four analysts (market, sentiment, news, fundamentals).
  - `tradingagents/agents/researchers/` — Bull/Bear researchers.
  - `tradingagents/agents/managers/` — Research Manager, Portfolio Manager.
  - `tradingagents/agents/trader/` — Trader.
  - `tradingagents/agents/risk_mgmt/` — Aggressive/Neutral/Conservative analysts.
  - `tradingagents/graph/` — graph setup, propagation, conditional logic, checkpointing.
  - `tradingagents/dataflows/` — vendor routing and data adapters.
  - `tradingagents/llm_clients/` — provider clients.
  - `tradingagents/memory/` — memory log + settlement/reflection.
  - `cli/` — CLI entry and display.
  - `eval/` — the NFR-E1 evaluation harness.
  - `scripts/ci/` — the six blocking gates.
- Module names match architectural elements. A new file must reference the ADR
  and invariant it implements.

## 4. Readable / modifiable / frozen

| Path | Status |
|---|---|
| `tradingagents/`, `cli/` | Modifiable under the constraints below and `.opencode/permissions.jsonc`. |
| `tests/`, `eval/`, `scripts/ci/` | Modifiable; tests are added/extended, never weakened to pass. |
| `docs/`, `transcripts/` | Modifiable (docs). |
| `.github/workflows/` | Modifiable only for gate changes approved by the team. |
| `AGENTS.md`, `Prompt.md`, `architecture-blueprint.md`, `.opencode/rules.md`, `.agent/rules.md` | **Human-only**; changes require an architecture decision. |
| `.env*`, secrets, credentials | **Frozen**; never read or commit secrets. |
| `CHANGELOG.md`, `LICENSE`, upstream `assets/` | Frozen unless an explicit task targets them. |

## 5. Integration contracts between modules

- **State contract**: graph state keys are declared in
  `tradingagents/agents/state.py` (`AgentState`). Adding a key is additive; do
  not repurpose an existing key.
- **Vendor contract**: data access goes through `tradingagents/dataflows/router.py`
  (`VENDOR_METHODS`); do not call a vendor directly from an agent.
- **LLM contract**: model creation goes through `tradingagents/llm_clients`
  (`create_tier_client`); never instantiate a provider client inline.
- **Structured-output contract**: decision agents use the schemas in
  `tradingagents/agents/schemas.py` via `tradingagents/agents/structured.py`;
  a failed structured parse is marked DEGRADED, never silently dropped.
- **Eval contract**: the harness patches only through the `Source`/`LLMSource`
  protocols in `eval/sources.py`; it must not modify production behavior.
- **Authority boundary**: model output is advisory; deterministic code (risk gate,
  rating integrity, budget) is authoritative. See `architecture-blueprint.md` §4.

## 6. Verification requirements for generated code

- Every fit criterion in `docs/req/requirements.yaml` has at least one test
  (see `docs/code-governance/verification-constraints.md`).
- Every invariant in `docs/architecture/invariants.md` has a test that fails when
  the invariant is violated (at least one negative test per feature).
- Every test references the requirement/invariant it verifies.
- New work runs all previous tests with zero regressions
  (`scripts/ci/check_regression.py`).
- The six blocking gates must pass before merge; gate 1 (test-approval) requires
  a completed `docs/evidence/e1/test-approval.md`.
- Do not weaken or delete a test to make a gate pass. Fix the code.

## 7. Plan-first rule

Read `Prompt.md`. Before writing code for any non-trivial change, produce an
execution plan (traceability, interface contract, scope boundaries, testing
strategy, steps) and **stop for human approval**. Do not run unattended to
completion.
