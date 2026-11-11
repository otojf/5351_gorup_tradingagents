# ADR-001: Offline Reproducible Evaluation Harness

- Status: Implemented on the `feat/nfr-e1-eval` feature branch (slices 1-3),
  pending team review and merge.
- Date: 2026-11-11
- Owner: E
- Requirement: NFR-E1 (with nested FR-E1, FR-E2, FR-E3, INV-E1)
- Baseline: team commit `46bde74`; upstream TradingAgents v0.7.1 (`9fa1196`)

This ADR records an architecture decision for the evaluation harness. It
distinguishes what the harness proves (structural determinism under a fixed
scripted source) from what it does not (real-input reproducibility, which needs
recorded replay, FR-E4).

## 1. Context

The TradingAgents baseline runs a LangGraph pipeline of analysts -> researchers ->
trader -> risk debate -> portfolio manager, producing a final rating and Markdown
reports. The baseline has:

- no fixed evaluation set (no golden cases),
- no per-run manifest recording what produced a run,
- no before/after comparison to show an enhancement is real,
- data gathered live from vendors and LLMs (non-deterministic, paid, networked).

NFR-E1 requires reproducible fixed-case evaluation: stable ratings and metrics
under the same commit/config/data, an offline suite that completes in bounded
time, and six blocking CI gates. FR-E1 (golden set + comparison), FR-E2 (manifest),
FR-E3 (six gates) and INV-E1 (no merge with a failing gate) are its nested
supporting requirements.

The core tension: the real pipeline is non-deterministic and networked, but a
reproducible evaluation must be deterministic and offline. Something must stand in
for the live vendors and LLMs without changing production code.

## 2. Scope

In scope:

- A golden set of fixed `(ticker, date)` cases.
- An offline runner that drives the real graph with scripted data + a scripted
  model, recording a per-run manifest.
- Repeat-run stability checks and a before/after comparison table.
- (Later phases) six CI gates and the no-merge invariant.

Out of scope (not approved for this stage):

- Real-input reproducibility via recording/replay (FR-E4).
- Physically migrating `src/` / `test/offline|live` (a structural mapping is
  documented instead; see `repository-structure-mapping.md`).
- Any change to `tradingagents/` production behavior.

## 3. Architecture candidates

### A. Standalone runner with no graph contact
Build a separate script that mimics the pipeline. Rejected: it would test a
replica, not the real graph; determinism would say nothing about the shipped code.

### B. Fake vendors only, real LLM
Stub data vendors but call the real model. Rejected: LLM output is
non-deterministic and networked, so ratings cannot be stable or run offline; cost
and latency violate the offline requirement.

### C. Full recording/replay now (FR-E4)
Record live LLM + vendor responses and replay them. Rejected for this stage: it
is the heavier option, needs an initial network capture per case, and is itself a
separate requirement. The scripted source's interfaces are shaped to accommodate
replay later.

### D. Scripted source + real graph, protocol-shaped for future replay (selected)

Drive the **real** graph (`TradingAgentsGraph.stream_run`) with:

- a `Source` that patches the same vendor/data points the offline end-to-end test
  already patches (`tradingagents.dataflows.router` vendor methods, OHLCV snapshot,
  instrument identity), and
- an `LLMSource` that patches `create_tier_client` with a `ScriptedModel`.

Both are behind `Source` / `LLMSource` protocols that also return a `snapshot_id`,
so a recording implementation (FR-E4) can be dropped in without changing the
runner. No production code is modified; the patches live only inside an
`EvalContext`.

## 4. Decision

Adopt **D**: a scripted source behind stable protocols, driving the real graph,
with a per-run manifest.

### 4.1 Determinism boundary (explicit)

- Proven: under a fixed scripted source, the harness and graph structure produce
  repeatable ratings, reports and token counts; runs are isolated (own `run_id`,
  results dir, memory/state log).
- Not proven: real-input reproducibility. The scripted source is not real market
  or LLM data; recording/replay (FR-E4) is required to make that claim.

This boundary is stated in `eval/sources.py`, `eval/manifest.py`'s `scope_note`,
and the evidence README.

### 4.2 Runner uses `stream_run`, not `propagate`

`propagate` does not put callbacks into the graph config, so tool events and token
usage would be lost. `stream_run` forwards the config and yields each `ToolMessage`,
which is the authoritative tool-call count (independent of the callback path).

### 4.3 Manifest is honest about missing fields

Fields the baseline cannot supply (degradations, risk verdicts, traceability) are
recorded as `null` with a reason in `unavailable_sources`, never faked. They are
filled by owners A/B/D when their branches merge.

## 5. AI component — layered context structure

For the LLM component, the designed structure the model receives on every turn,
the assembly pipeline, the token budget, and the re-injection policy:

### 5.1 Layers received each turn

| Layer | Contents |
|---|---|
| Identity | Instrument identity (resolved ticker/company/asset type) and agent role. |
| Standing constraints | Immutable behavioral rules (no fabricated prices, cite evidence, respect analysis date). |
| Retrieved knowledge | Analyst reports, tool outputs, memory-log lessons relevant to this ticker/date. |
| Conversation history | Prior debate/research turns for this run. |
| Resumable state | Checkpointed state so an interrupted run continues rather than restarts. |
| Current task | The specific node's instruction (e.g., write the market report, propose a trade). |

### 5.2 Assembly pipeline

`deduplicate -> prioritize -> budget -> compact -> assemble`:

1. Deduplicate repeated reports/tool output.
2. Prioritize standing constraints and the current task above retrieved history.
3. Budget: apply the token cap (below).
4. Compact: summarize/drop low-priority history to fit.
5. Assemble the final layered prompt.

### 5.3 Token budget and compaction threshold

- Per-run token cap: enforced by owner C's budget mechanism (NFR-C1); the harness
  records tokens per run in the manifest.
- Compaction threshold: when the assembled prompt would exceed the cap, compact
  the conversation-history layer first (summarize oldest turns), then retrieved
  knowledge, never the standing constraints or current task.
- Compaction records its reason in the run (degradations/budget fields), so it is
  visible, not silent.

### 5.4 Re-injecting critical constraints after compaction

After any compaction, the identity layer, standing constraints, and the current
task are **re-injected verbatim** so safety-relevant rules never fall out of
context. This re-injection is deterministic and applied by the assembly step, not
left to the model.

Note: budget/compaction enforcement is owner C's (NFR-C1); this ADR fixes the eval
harness's design position and the boundary that the harness only observes and
records these, it does not implement the budget.

## 6. Consequences

Positive:

- Real graph is exercised; determinism claim is about the shipped structure.
- Protocols make FR-E4 replay a drop-in later.
- Offline, no network, no cost; fits CI.
- Manifest + comparison make before/after differences auditable.

Negative / trade-offs:

- Does not prove real-input reproducibility; that is explicit and deferred.
- Scripted source must keep pace with vendor/router patch points; if those change,
  the harness breaks (a useful early warning, but maintenance cost).
- Manifest fields depending on A/B/D are null until their branches merge.

## 7. Conditions that would reopen this decision

- FR-E4 (recorded replay) is approved: the `Source`/`LLMSource` protocols are
  extended with a recording implementation; the runner should not change.
- Real market/LLM data becomes required for the evaluation claim: switch the
  active source to a recording source.
- The graph's entry points change (e.g., `stream_run` removed or callback wiring
  changes): the runner's tool-count method must be revisited.
- Owners A/B/D merge: fill `degradations`, `risk_verdicts`, `traceability` in the
  manifest and remove their entries from `unavailable_sources`.
