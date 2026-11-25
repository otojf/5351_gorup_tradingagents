# Architecture Blueprint (D2.1)

The master constraint document the coding agent reads before any work. It states
scope, architectural drivers, system boundaries, components, authority boundaries
(advisory vs authoritative), the agent workflow, permissions, verification
strategy, observability, and the change policy.

Baseline: TradingAgents v0.7.1 (`9fa1196`), team commit `46bde74`. This blueprint
constrains an **extension** of that baseline; it does not replace it.

> This document describes the integrated system on `main`: the baseline graph,
> the FR-A1 risk gate, the FR-B2 citation checker, FR-C2 vendor skip, FR-D2
> structured-output degradation, the NFR-E1 evaluation harness, and the six CI
> gates. The token budget (NFR-C1) remains partial; where a component is not
> delivered, the document says so instead of marking it "external".

## 1. Scope

TradingAgents is a multi-agent LLM system that analyses a ticker on a trade date
and produces a five-tier investment rating (`Buy`, `Overweight`, `Hold`,
`Underweight`, `Sell`, or `REVIEW` when no parseable rating exists). The project
adds, around this baseline:

- a **deterministic risk gate** at the Portfolio Manager output boundary
  (FR-A1 / INV-A1 / NFR-A1 / NFR-A2);
- a **conclusion citation checker** (FR-B2; FR-B1 remains partial);
- **run-scoped FRED skip state** for missing credentials (FR-C2; NFR-C1 remains
  partial);
- **visible structured-output degradation** with two retries and a DEGRADED
  marker (FR-D2 / INV-D1);
- a **reproducible offline evaluation harness** (NFR-E1: golden set, run
  manifest, before/after comparison); and
- **six blocking CI gates** (D7) with a test-approval human gate, a secret scan,
  and the no-merge-with-failing-gate invariant.

Out of scope: real-input reproducibility via recorded replay (FR-E4), the token
budget/circuit breaker (NFR-C1 is partial), and the human approval queue for
`NEEDS_REVIEW` decisions (FR-A2).

## 2. Architectural drivers

1. **Reproducibility** — the same commit/config/data must yield stable ratings
   and metrics.
2. **Offline & bounded** — the evaluation suite runs offline within a fixed time
   bound, so it can run in CI.
3. **Auditability** — every run records what produced it (manifest); every
   requirement traces to a component, a test, and a monitor.
4. **Safety boundary** — model output is advisory; deterministic code decides
   (rating integrity and the risk gate; the token budget is not implemented).
5. **Governance** — agent changes are gated; safety-critical paths require an
   architecture decision and human approval.

## 3. System boundaries

```
CLI (src/cli/) ──► TradingAgentsGraph (src/tradingagents/graph) ──► LangGraph pipeline
                    │                                          │
                    │  data via src/tradingagents/dataflows/router.py  │ reports + final state
                    │  models via src/tradingagents/llm_clients        ▼
                    │                                    memory log (src/tradingagents/memory)
                    └── state keys in src/tradingagents/agents/state.py

src/eval/ (offline harness) ── patches Source/LLMSource ──► drives the real graph
scripts/ci/ (six gates) ── validate registry, eval, tests, AI-use log
```

- Data enters only through `src/tradingagents/dataflows/router.py` (`VENDOR_METHODS`).
- Models are created only through `src/tradingagents/llm_clients.create_tier_client`.
- The eval harness sits **outside** production behavior: it only patches through
  the `Source`/`LLMSource` protocols in `src/eval/sources.py`.

## 4. Authority boundaries (advisory vs authoritative)

| Concern | Advisory (model) | Authoritative (deterministic) |
|---|---|---|
| Final rating | The Portfolio Manager's model rating | `src/tradingagents/agents/rating.py` (`run_rating`) normalises it; unparseable → `REVIEW` |
| Tool calls | The model requests them | `src/cli/stats_handler.py` counts `on_tool_start`; the runner counts finished `ToolMessage`s |
| Data | — | Vendor router + cached snapshots serve point-in-time data |
| Risk (owner A) | Model reasoning | Deterministic risk gate in `src/tradingagents/risk_gate/`; a missing or invalid portfolio fails closed to `REVIEW` |
| Citation (owner B) | Model-written report | `src/fr_b2/` resolves claims against registered evidence; unresolved claims are `UNTRACEABLE` |
| Budget (owner C) | Model output length | **Not implemented** (NFR-C1 partial); FR-C2 only skips an unconfigured FRED source |
| Eval result | — | The manifest records what actually ran; `compare` computes deltas |

Model output never overrides deterministic code on a safety-relevant path.

## 5. Components

- **Analysts** (`src/tradingagents/agents/analysts/`): market, sentiment, news,
  fundamentals; each an isolated sub-graph that calls tools then files a report.
- **Researchers** (`src/tradingagents/agents/researchers/`): Bull vs Bear debate.
- **Managers** (`src/tradingagents/agents/managers/`): Research Manager
  (investment plan), Portfolio Manager (final decision + rating).
- **Trader** (`src/tradingagents/agents/trader/`): trade proposal.
- **Risk debate** (`src/tradingagents/agents/risk_mgmt/`):
  Aggressive/Neutral/Conservative.
- **Graph** (`src/tradingagents/graph/`): setup, propagation, conditional logic,
  checkpointing. Analysts run in parallel; the memory step runs alongside them.
- **Dataflows** (`src/tradingagents/dataflows/`): vendor routing and adapters.
- **LLM clients** (`src/tradingagents/llm_clients/`): provider clients.
- **Memory** (`src/tradingagents/memory/`): log + settlement/reflection.
- **Risk gate** (`src/tradingagents/risk_gate/`): deterministic policy engine
  and Portfolio Manager adapter.
- **Citation checker** (`src/fr_b2/`): offline claim/evidence resolution.
- **CLI** (`src/cli/`): entry and display.
- **Eval harness** (`src/eval/`): `golden.py`, `sources.py`, `runner.py`,
  `manifest.py`, `compare.py`.
- **CI gates** (`scripts/ci/`): six gate scripts plus the permission/secret
  checks used by gate 2.

## 6. Agent workflow (graph)

```
START ──► [Market | Sentiment | News | Fundamentals analysts] (parallel)
      ──► Bull ⇄ Bear (debate) ──► Research Manager
      ──► Trader ──► [Aggressive | Neutral | Conservative] (risk debate)
      ──► Portfolio Manager ──► END
Memory Log step runs alongside the analysts.
```

## 7. Permissions

See `.opencode/permissions.jsonc` (machine-readable) and
`.opencode/rules.md` / `.agent/rules.md` (behavioral). Default is no read, no
write; every path is explicitly whitelisted. Human-only files are listed in
`AGENTS.md` §4.

## 8. Verification strategy

- Fit criterion → at least one test; invariant → a negative test that fails when
  violated (see `docs/code-governance/verification-constraints.md`).
- Three tiers: structural (layering, permissions, fitness functions), regression
  (all prior suites pass), behavioral (quality thresholds, zero safety escapes).
- Six blocking gates in `.github/workflows/ci.yml`; branch protection requires
  nine checks + one approving review. Gate 2 includes mypy on the
  safety-critical modules, a permission-model check, a secret scan, and the
  contract/API-surface checks; the full-repo type-check remains debt.

## 9. Observability

- `src/cli/stats_handler.py` records LLM calls, tool calls, tokens in/out.
- The eval manifest records commit, model, config hash, prompt/data snapshot,
  tokens, latency, tool calls, and honest `null`s with reasons for fields the
  baseline cannot yet supply.
- Trace matrix maps every requirement to a runtime monitor.

## 10. Change policy

- Safety-critical code changes require an architecture decision (ADR) and human
  approval; see `.agent/rules.md`.
- Read `Prompt.md`: plan-first, then stop for human approval.
- The six gates must pass before merge; do not weaken tests to pass a gate.
