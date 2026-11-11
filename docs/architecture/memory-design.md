# Memory / State Design (D2.5)

What state survives across sessions, interruptions, and versions; the write and
retrieval policy; ownership; retention; and privacy.

## 1. Two kinds of state

### 1.1 In-run graph state

Declared in `tradingagents/agents/state.py` (`AgentState`, `MessagesState`).
Per-run keys include `company_of_interest`, `trade_date`, `asset_type`,
`instrument_context`, the four analyst reports, `investment_debate_state`,
`investment_plan`, `trader_investment_plan`, `risk_debate_state`,
`final_trade_decision`, `final_rating`, `past_context`, `memory_note`, and
`portfolio_context`. This state is per-run; it does not persist between runs
unless checkpointed (below).

### 1.2 Cross-run memory log

`tradingagents/memory/` (`log.py`, `settlement.py`, `reflection.py`) stores past
decisions and lessons. The Memory Log graph step settles due past decisions and
loads lessons relevant to the ticker/date for the Portfolio Manager
(`past_context`).

## 2. Persistence and survival

| Concern | Behavior | Source |
|---|---|---|
| Interruptions | Checkpointing (when `checkpoint_enabled`) recompiles the graph with a per-ticker SQLite saver; a run resumes from the last successful node. | `tradingagents/graph/checkpointer.py` |
| Across runs | The memory log persists decisions and lessons; settlement resolves due decisions on later runs. | `tradingagents/memory/` |
| Across versions | The checkpoint thread id embeds a run signature (analysts, debate/risk depth, settings digest, layout) so a version change starts fresh instead of resuming stale state. | `tradingagent/graph/trading_graph.py` (`_run_signature`) |
| Eval runs | Each run gets an isolated `run_id`, results dir, and memory/state log, so runs never feed into each other. | `eval/runner.py` |

## 3. Write / retrieval policy

- Write: a completed run records its decision into the memory log
  (`record_decision`). Settlement writes reflections for due decisions.
- Retrieval: the Portfolio Manager reads `past_context` filtered to lessons known
  by the trade date (`_memory_as_of`): a historical/backtest run never sees
  future lessons.

## 4. Ownership

- The memory log is owned by the memory subsystem; agents write only through its
  API.
- The eval harness owns its per-run logs and never mutates production memory.

## 5. Retention

- TODO (team): state the retention window for the memory log and results dirs.
  Current behavior: results and logs are written under `results_dir` and
  `data_cache_dir`; pruning is manual.

## 6. Privacy

- The memory log stores decision text and ratings, not credentials.
- Portfolio context is caller-supplied and rendered per run; it is not persisted
  in the shared log.
- No secrets are written to state or logs (see `.agent/rules.md`).
