# .agent/rules.md — Project Covenant (D3)

> Human-only file. Changes require an architecture decision.

The covenant between the team and the agent: abstraction limits, dependency
constraints, test independence, safety-critical change approval, and context
freshness.

## 1. Abstraction limits

- Work at the level the requirement names. Do not introduce new abstractions,
  indirection layers, or frameworks beyond what the requirement and ADR justify.
- Prefer extending an existing module over adding a new one. A new module states
  the ADR and invariant it implements.

## 2. Dependency constraints

- No new third-party dependency without team approval and a stated reason; add it
  to `pyproject.toml` (dev extras for tooling) and mention it in the review memo.
- Network access only through `tradingagents/dataflows/`; LLM providers only
  through `tradingagents/llm_clients/`.
- Tests are offline by default; anything requiring API access uses the
  `integration` marker and is excluded from the default run.

## 3. Test independence and negative tests

- Tests are independent: no test depends on another test's leftover state; each
  run isolates its `run_id`, results dir, and memory/state log.
- **At least one negative test per feature:** a test that fails when the feature's
  safety behavior regresses.

## 4. Safety-critical code changes

Changing safety-critical code (rating normalization, risk gate, budget cap,
structured-output degradation handling) requires:

1. an architecture decision (ADR), and
2. human approval before implementation.

The agent must stop and request approval; it must not self-approve.

## 5. Context freshness

- Rules and architecture artifacts are updated within **one sprint** of a
  requirements change, so the agent never reads stale constraints.
- If a requirement changes and the docs are not yet updated, the agent flags the
  mismatch and stops rather than proceeding on stale context.

## 6. Secrets

- Never read, log, or commit secrets. Reports redact credentials.
