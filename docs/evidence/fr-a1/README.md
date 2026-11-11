# FR-A1 — Deterministic Risk Gate (Team Handoff)

FR-A1 adds a **deterministic, offline, auditable risk gate** to TradingAgents. Before
any trade decision is published, it validates the model's structured `TraderProposal`
and `PortfolioDecision` against a versioned policy and returns an independent verdict:
`APPROVED` / `REJECTED` / `NEEDS_REVIEW`. It never approves a decision on missing data.
All work is on branch `feat/fr-a1-risk-gate`; baseline is `46bde74` (TradingAgents
v0.7.1).

Authoritative detail lives in the existing documents — this README only orients you:

- ADR: [`docs/architecture/adr/adr-fr-a1-risk-gate.md`](../../architecture/adr/adr-fr-a1-risk-gate.md)
- Test plan: [`docs/req/fr-a1-test-plan.md`](../../req/fr-a1-test-plan.md)
- Demo: [`docs/evidence/fr-a1/demo/README.md`](demo/README.md)
- Verification capture: [`docs/evidence/fr-a1/verification/README.md`](verification/README.md)
- Open decisions / dependencies: [`remaining-dependencies.md`](remaining-dependencies.md)

## 1. Rules (v1, cash-funded long BUY)

| ID | Rule |
|---|---|
| `R1_STOP_LOSS_REQUIRED` | An actionable long BUY must carry a stop-loss. |
| `R2_SINGLE_NAME_CAP` | Projected single-name weight ≤ 10% (`0.10`) and the BUY must increase the position. |
| `R3_SECTOR_CONCENTRATION` | Projected affected-sector exposure ≤ 30% (`0.30`). |
| `R4_REWARD_RISK` | Direction-aware reward-to-risk ≥ 1.5 with `stop < entry < target`; prices strictly positive. |
| `R5_BLACKLIST` | Ticker not on the versioned blacklist. |
| `R6_INPUT_INTEGRITY` | Structured inputs present, finite, consistent, direction unambiguous, affordable. |
| `R0_ALL_RULES_PASSED` | Positive marker so every verdict carries a rule ID. |

Each rule is `PASS` / `VIOLATED` / `NOT_APPLICABLE` / `UNKNOWN`. `UNKNOWN` (insufficient
input) is **not** `VIOLATED`. Aggregation precedence is
`REJECTED > NEEDS_REVIEW > APPROVED`; every applicable rule is evaluated (no
first-fail short-circuit). Policy `fr-a1-v1` defaults: single-name cap `0.10`, sector
cap `0.30`, min reward/risk `1.5`, injectable blacklist.

## 2. New modules (`tradingagents/risk_gate/`)

- `models.py` — Pydantic inputs (`RiskInputs`, `TargetPosition`, `Holding`,
  `PortfolioRiskSnapshot`), outputs (`RuleResult`, `RiskEvaluation`,
  `RiskAuditRecord`), and the `RiskVerdict`/`DecisionStatus`/`RuleOutcome` enums.
- `policy.py` — immutable `RiskPolicy` with stable SHA-256 `policy_hash` (changes when
  any threshold or the normalized blacklist changes).
- `sizing.py` — `target_position_weight` validation and projected market value.
- `portfolio_snapshot.py` — snapshot consistency (`cash + Σ market_value ==
  portfolio_value`), valuation-date check, sector normalization/conflict detection,
  projected sector exposure.
- `engine.py` — pure `evaluate_risk(inputs, policy)` and `audit_id_for(...)`. No
  network, file I/O, LLM, or LangGraph.
- `adapter.py` — `build_inputs`, `apply_gate` (evaluate once, persist audit, return
  state updates), `persist_audit` (durable JSON writer); enforces
  audit-before-publication.

The core engine modules import nothing from LangGraph/network/LLM.

## 3. Existing TradingAgents files modified (all additive)

- `tradingagents/agents/state.py` — new state keys: `trader_proposal`,
  `portfolio_decision`, `model_rating`, `risk_verdict`, `decision_status`,
  `risk_evaluation`.
- `tradingagents/agents/trader/trader.py` — retain the structured `trader_proposal`
  alongside the unchanged rendered string (free-text fallback leaves it `None`).
- `tradingagents/agents/managers/portfolio_manager.py` — run `apply_gate` once at the
  output boundary; set `final_rating` to the effective signal; preserve
  `model_rating`.
- `tradingagents/graph/trading_graph.py` — add `risk_gate=v1` to the run signature
  (checkpoint reset) and persist `risk_verdict`, `decision_status`, `model_rating`,
  `risk_evaluation`, `policy_version`, `policy_hash` in `_log_state`.

## 4. Integration point and data flow

The gate runs **once**, at the Portfolio Manager output boundary — after both
structured objects exist and before any consumer reads `final_rating`.

```
Trader node ──► trader_proposal (structured)
                       │
risk debators ─────────┤
                       ▼
Portfolio Manager node ──► portfolio_decision (structured, has model rating)
                       │
                       ▼
            apply_gate(ticker, trade_date, trader_proposal,
                       portfolio_decision, risk_portfolio, audit_dir=…)
                       │
        ┌──────────────┼─────────────────────────────┐
        ▼              ▼                             ▼
 RiskEvaluation   persist_audit (durable,   state updates:
 (verdict, rule   before publication)       model_rating, final_rating,
  results)                                   risk_verdict, decision_status,
                                             risk_evaluation
                       │
                       ▼
     final_rating (effective) ──► propagate signal, state log, memory,
                                   reports, HTML badge, CLI
```

Three concepts stay distinct: `model_rating` (the model's own rating, preserved as
evidence), `risk_verdict` (gate-only), and `final_rating` (effective public signal).
`final_rating` is the model rating **only** when `APPROVED`/`ACTIONABLE`; otherwise it is
the existing `REVIEW` sentinel, so a blocked BUY cannot leak as actionable.

## 5. Structured contracts

**Inputs** (`build_inputs` / `apply_gate`), from structured decisions plus an optional
additive config `risk_portfolio`:

```python
risk_portfolio = {
    "snapshot": {                      # PortfolioRiskSnapshot
        "valuation_date": "2026-01-09", # must equal the run's trade_date
        "portfolio_value": 1_000_000.0,
        "cash": 830_000.0,
        "holdings": [
            {"ticker": "NVDA", "market_value": 20_000.0, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 150_000.0, "sector": "Technology"},
        ],
    },
    "target_position": {"target_position_weight": 0.05, "sector": "Technology"},
}
```

**Output** of `apply_gate` — a state-update dict:

```python
{
    "model_rating": str | None,      # preserved model rating
    "final_rating": str,             # effective public signal (model rating or REVIEW)
    "risk_verdict": "APPROVED" | "REJECTED" | "NEEDS_REVIEW",
    "decision_status": "ACTIONABLE" | "BLOCKED" | "PENDING_REVIEW" | "NO_TRADE",
    "risk_evaluation": RiskEvaluation,  # verdict, rule_results, policy_hash, input_snapshot, …
}
```

## 6. How other members should use the gate

- **Via the graph (supported path):** supply the portfolio contract through config —
  `TradingAgentsGraph(config={"risk_portfolio": {...}})`. The PM node calls the gate;
  read `state["final_rating"]`, `state["risk_verdict"]`, `state["decision_status"]`,
  `state["model_rating"]`, `state["risk_evaluation"]`.
- **Directly (unit-level):** `from tradingagents.risk_gate import evaluate_risk,
  RiskInputs, RiskPolicy` for the pure engine, or
  `from tradingagents.risk_gate.adapter import apply_gate` for the full
  evaluate + audit path.
- **Do not** parse Markdown to drive the gate or invent market values, sectors,
  weights, or prices. Missing/ambiguous data yields `NEEDS_REVIEW`, not approval.
- Presence of a `results_dir` causes a per-ticker `risk_audit/` JSON record; without
  it, an otherwise-`APPROVED` decision downgrades to `NEEDS_REVIEW`.

## 7. Reproducible commands (from repo root, offline)

```bash
# Lint the FR-A1 + touched packages
python -m ruff check tradingagents/risk_gate tradingagents/agents tradingagents/graph tests/risk_gate

# FR-A1 suite
python -m pytest tests/risk_gate -q

# Full baseline regression (excluding FR-A1)
python -m pytest -q --ignore=tests/risk_gate

# Self-checking deterministic demo (no network, no LLM; exit 0 only if all checks pass)
python docs/evidence/fr-a1/demo/run_demo.py
```

## 8. Verified results

Two distinct artifacts, captured at different times:

**Test/lint evidence** — captured at commit `e716596` in
[`verification/test-results.txt`](verification/test-results.txt):

| Step | Result | Exit |
|---|---|---|
| Ruff | All checks passed | 0 |
| `tests/risk_gate` | 239 passed, 1 xpassed | 0 |
| Baseline (excluding FR-A1) | 1412 passed, 1 skipped, 1 deselected, 100 subtests | 0 |

**Demo** — added later, after `e716596` (evidence-packaging commit); its output is
captured in [`demo/demo-output.txt`](demo/demo-output.txt):

| Step | Result | Exit |
|---|---|---|
| `run_demo.py` | `SUMMARY: 8/8 expectancy checks passed` | 0 |

The 1 xpass is the documented non-strict SELL proposal (pending decision P2); the 1
skip is `test_bedrock_provider.py` (`langchain_aws` not installed), unrelated.

## 9. Known limitations and fail-closed behavior

- **Fail-closed by design:** a run without `risk_portfolio` surfaces `REVIEW`; missing
  structured Trader action or PM rating → R6 `UNKNOWN`; missing audit destination or a
  failed audit write → non-actionable (never `ACTIONABLE` without a durable audit).
- **Durability:** `persist_audit` writes and closes a JSON file but does **not**
  `fsync` — "written before publication", not crash-level durability.
- **Trade scope:** only ordinary cash-funded long BUY is fully supported. HOLD is
  `NO_TRADE`; unsupported SELL/short is never approved in v1.
- **No CLI flag** for `risk_portfolio`; the supported path is the Python API. The
  default CLI fails closed.
- **Intentional baseline change:** runs without `risk_portfolio` now surface `REVIEW`
  instead of the model rating — this is an approved safety migration, not a regression.
- Pending policy decisions (P1 HOLD-vs-R4, P2 SELL criteria, P6 sector-cap scope,
  blacklist source) are listed in `remaining-dependencies.md`.

## 10. Dependencies on other group modules

- **Owner D (structured adapter):** the gate consumes `TraderProposal` /
  `PortfolioDecision`. If D's structured path degrades to free text, the gate fails
  closed (`NEEDS_REVIEW`); safe, but approval requires D's structured path to be
  healthy.
- **Owner E (eval harness / manifest / CI):** the state log now carries
  `risk_verdict`, `decision_status`, `model_rating`, `policy_version`, `policy_hash`,
  and the redacted `risk_evaluation`. E's manifest schema must include
  `risk verdicts` / `policy_version`, and its blocking CI gates must cover
  `tests/risk_gate`.
- **Owners B/C:** no hard dependency for FR-A1 correctness (evidence refs and token
  budget are independent).
- **FR-A2 / FR-A3:** out of scope. FR-A1 emits `NEEDS_REVIEW` and blocks automatic
  execution; the human approval queue (FR-A2) and runtime-reloadable thresholds
  (FR-A3) are deferred.
