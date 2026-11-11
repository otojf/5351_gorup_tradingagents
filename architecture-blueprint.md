# Architecture Blueprint (D2.1)

The master constraint document the coding agent reads before any work. It states
scope, architectural drivers, system boundaries, components, authority boundaries
(advisory vs authoritative), the agent workflow, permissions, verification
strategy, observability, and the change policy.

Baseline: TradingAgents v0.7.1 (`9fa1196`), team commit `46bde74`. This blueprint
constrains an **extension** of that baseline; it does not replace it.

> This document focuses on what is implemented on this repository (the NFR-E1
> evaluation harness and the six CI gates). Components owned by other feature
> branches are named where they intersect, and marked as externally owned.

## 1. Scope

TradingAgents is a multi-agent LLM system that analyses a ticker on a trade date
and produces a five-tier investment rating (`Buy`, `Overweight`, `Hold`,
`Underweight`, `Sell`, or `REVIEW` when no parseable rating exists). The project
adds, around this baseline:

- a **reproducible offline evaluation harness** (NFR-E1: golden set, run
  manifest, before/after comparison), and
- **six blocking CI gates** (D7) with a test-approval human gate and the
  no-merge-with-failing-gate invariant.

Out of scope here: real-input reproducibility via recorded replay (FR-E4), the
deterministic risk gate (FR-A1, owner A), structured-evidence tracing (FR-B1,
owner B), and the token budget (NFR-C1, owner C) — all named where they
interface.

## 2. Architectural drivers

1. **Reproducibility** — the same commit/config/data must yield stable ratings
   and metrics.
2. **Offline & bounded** — the evaluation suite runs offline within a fixed time
   bound, so it can run in CI.
3. **Auditability** — every run records what produced it (manifest); every
   requirement traces to a component, a test, and a monitor.
4. **Safety boundary** — model output is advisory; deterministic code decides
   (rating integrity, risk gate, budget).
5. **Governance** — agent changes are gated; safety-critical paths require an
   architecture decision and human approval.

## 3. System boundaries

```
CLI (cli/) ──► TradingAgentsGraph (tradingagents/graph) ──► LangGraph pipeline
                    │                                          │
                    │  data via dataflows/router.py            │ reports + final state
                    │  models via llm_clients                  ▼
                    │                                    memory log (tradingagents/memory)
                    └── state keys in agents/state.py

eval/ (offline harness) ── patches Source/LLMSource ──► drives the real graph
scripts/ci/ (six gates) ── validate registry, eval, tests, AI-use log
```

- Data enters only through `tradingagents/dataflows/router.py` (`VENDOR_METHODS`).
- Models are created only through `tradingagents/llm_clients.create_tier_client`.
- The eval harness sits **outside** production behavior: it only patches through
  the `Source`/`LLMSource` protocols in `eval/sources.py`.

## 4. Authority boundaries (advisory vs authoritative)

| Concern | Advisory (model) | Authoritative (deterministic) |
|---|---|---|
| Final rating | The Portfolio Manager's model rating | `tradingagents/agents/rating.py` (`run_rating`) normalises it; unparseable → `REVIEW` |
| Tool calls | The model requests them | `cli/stats_handler.py` counts `on_tool_start`; the runner counts finished `ToolMessage`s |
| Data | — | Vendor router + cached snapshots serve point-in-time data |
| Risk (owner A) | Model reasoning | Deterministic risk gate (external branch) |
| Budget (owner C) | Model output length | Deterministic token cap (external branch) |
| Eval result | — | The manifest records what actually ran; `compare` computes deltas |

Model output never overrides deterministic code on a safety-relevant path.

## 5. Components

- **Analysts** (`tradingagents/agents/analysts/`): market, sentiment, news,
  fundamentals; each an isolated sub-graph that calls tools then files a report.
- **Researchers** (`agents/researchers/`): Bull vs Bear debate.
- **Managers** (`agents/managers/`): Research Manager (investment plan),
  Portfolio Manager (final decision + rating).
- **Trader** (`agents/trader/`): trade proposal.
- **Risk debate** (`agents/risk_mgmt/`): Aggressive/Neutral/Conservative.
- **Graph** (`tradingagents/graph/`): setup, propagation, conditional logic,
  checkpointing. Analysts run in parallel; the memory step runs alongside them.
- **Dataflows** (`tradingagents/dataflows/`): vendor routing and adapters.
- **LLM clients** (`tradingagents/llm_clients/`): provider clients.
- **Memory** (`tradingagents/memory/`): log + settlement/reflection.
- **CLI** (`cli/`): entry and display.
- **Eval harness** (`eval/`): `golden.py`, `sources.py`, `runner.py`,
  `manifest.py`, `compare.py`.
- **CI gates** (`scripts/ci/`): six gate scripts.

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
  nine checks + one approving review.

## 9. Observability

- `cli/stats_handler.py` records LLM calls, tool calls, tokens in/out.
- The eval manifest records commit, model, config hash, prompt/data snapshot,
  tokens, latency, tool calls, and honest `null`s with reasons for fields the
  baseline cannot yet supply.
- Trace matrix maps every requirement to a runtime monitor.

## 10. Change policy

- Safety-critical code changes require an architecture decision (ADR) and human
  approval; see `.agent/rules.md`.
- Read `Prompt.md`: plan-first, then stop for human approval.
- The six gates must pass before merge; do not weaken tests to pass a gate.
