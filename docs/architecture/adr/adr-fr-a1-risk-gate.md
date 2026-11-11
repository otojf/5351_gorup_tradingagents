# ADR-FR-A1: Deterministic Risk Gate

- Status: Proposed (tests and design approved for authoring; production implementation
  blocked pending review of the written tests)
- Date: 2026-11-11
- Owner: A
- Requirement: FR-A1 (with INV-A1, NFR-A1, NFR-A2)
- Baseline: team commit `46bde74`; upstream TradingAgents v0.7.1 (`9fa1196`)

This ADR records an architecture decision **before** production implementation, as
required for a safety-critical change. It distinguishes newly generated work from
inherited baseline functionality.

## 1. Context

The TradingAgents baseline produces a final decision as Markdown:

- `TraderProposal` (`tradingagents/agents/schemas.py:146`) carries `action`,
  `reasoning`, `entry_price`, `stop_loss`, and free-text `position_sizing`.
- `PortfolioDecision` (`tradingagents/agents/schemas.py:221`) carries a 5-tier
  `rating`, `executive_summary`, `investment_thesis`, `price_target`, `time_horizon`.
- Both are rendered to Markdown (`render_trader_proposal`, `render_pm_decision`)
  and the Pydantic objects are **discarded**; only the strings
  (`trader_investment_plan`, `final_trade_decision`) and `final_rating` reach state.
- `PortfolioContext` (`tradingagents/portfolio.py:33`) has positions with only
  `ticker`, `quantity`, `average_price`; no market value, no sector.
- There is no deterministic final risk gate. `run_rating` passes model output
  through unchanged (`tradingagents/agents/rating.py:106`).

FR-A1 requires that before any trade decision is output, the system validates
`TraderProposal` and `PortfolioDecision` against a versioned policy, returning
`APPROVED` / `REJECTED` / `NEEDS_REVIEW` with rule IDs, and that decisions missing
a stop-loss or exceeding the single-name cap are never `APPROVED`.

## 2. Scope

In scope (this ADR and the accompanying test plan):

- FR-A1 core verdict, INV-A1 invariants, NFR-A1 (latency, no network), NFR-A2 (audit).

Out of scope (not approved for implementation in this stage):

- FR-A2 human approval queue. FR-A1 must *emit* `NEEDS_REVIEW` and block automatic
  execution, but the approval workflow itself is pending separate scope confirmation.
- FR-A3 advanced/configuration-driven policy thresholds.
- Features owned by B (evidence), C (token budget), D (structured adapter
  internals), E (eval harness, CI). FR-A1 depends on D's structured path but does
  not modify it.

## 3. Previous feasibility findings (verified against `46bde74`)

All prior read-only findings were re-verified in the current team repository. All
hold. One additional finding, material to the design: **structured objects are
discarded after rendering**, so a gate cannot rely on Markdown re-parsing.

## 4. Architecture candidates

### A. Guard inside the Portfolio Manager node
Evaluate inside `portfolio_manager_node`. Rejected: couples deterministic policy to
an LLM node, poor isolation for NFR-A1/A2, embeds approval logic in agent code.

### B. Dedicated Risk Gate graph node
Insert `Portfolio Manager → Risk Gate → END`. Pros: deterministic, isolable,
first-class audit in state. Cons: requires retaining structured objects; changes
graph shape and checkpoint signature; and a *separate node* is not by itself a
safety guarantee.

### C. Post-graph wrapper in `_run_graph` / `record_decision`
Cons: the CLI uses `stream_run` and calls `record_decision` itself
(`cli/run.py:353`), so a wrapper misses the CLI path; verdict is not in streamed
state.

### D. Pure engine + mandatory evaluation at the PM output boundary (selected)
Split into:

- a **pure, injectable engine** (`tradingagents/risk_gate/`) with no LangGraph,
  no network, no file I/O, no LLM, no dependency on a graph node; and
- an **integration layer** that guarantees evaluation happens before any public
  decision is emitted, at the Portfolio Manager output boundary.

The engine is the unit under test; the integration may be a graph node **and/or**
an invocation inside the manager boundary, but correctness must not depend on
"having a separate node". Publication is gated by the *enforcement point*, not by
graph topology.

## 5. Decision

Adopt **D**. Human review corrections (see §6) refine it as follows.

### 5.1 Authority boundary (safety enforcement)

A risk verdict must affect the *effective* recommendation at the public decision
boundary:

- The original model rating is preserved separately (`model_rating`).
- A `REJECTED` or `NEEDS_REVIEW` recommendation must **not** propagate as an
  actionable final recommendation. At the public boundary it is surfaced using the
  existing `REVIEW` sentinel semantics (`tradingagents/agents/rating.py:30`).
- No final recommendation may bypass risk evaluation. Both the programmatic API
  (`TradingAgentsGraph.propagate` returning a signal) and the CLI stream path
  (`cli/run.py`) must reflect the gate. Enforcement must be at a boundary that
  cannot publish before evaluation; if a graph node cannot guarantee that, the
  pure engine is invoked at the PM output boundary instead.

### 5.2 Verdict and actionability (kept distinct)

- `risk_verdict ∈ {APPROVED, REJECTED, NEEDS_REVIEW}`.
- `decision_status ∈ {ACTIONABLE, BLOCKED, PENDING_REVIEW, NO_TRADE}`:
  - `APPROVED` + actionable trade → `ACTIONABLE`
  - `REJECTED` → `BLOCKED`
  - `NEEDS_REVIEW` → `PENDING_REVIEW`
  - `APPROVED` + `HOLD` → `NO_TRADE` (an approved HOLD is not ACTIONABLE)
- Aggregation precedence: `REJECTED > NEEDS_REVIEW > APPROVED`. All applicable
  rule results are collected (no first-fail short circuit).
- Every evaluation produces a complete per-rule result set with rule identifiers,
  including successful evaluations. Rule outcomes are `PASS`, `VIOLATED`,
  `NOT_APPLICABLE`, or `UNKNOWN`. `UNKNOWN` (insufficient input to decide) is **not**
  the same as `VIOLATED` (a rule was broken): `triggered_violation_ids` contains
  only `VIOLATED` rule ids, while `evaluated_rule_ids` lists every rule considered.
  (For a missing stop-loss, `R1` is `VIOLATED` while `R4` may be `UNKNOWN`.)

### 5.2a Three separate concepts at the boundary

The system keeps three values distinct and never collapses them:

1. `model_rating` — the Portfolio Manager's own rating, preserved verbatim
   (`Buy`/`Overweight`/`Hold`/`Underweight`/`Sell`/`REVIEW`).
2. `risk_verdict` — `APPROVED` / `REJECTED` / `NEEDS_REVIEW`, from the gate only.
3. **effective public signal** — what the rest of the system may act on. The
   existing `final_rating` / `run_rating` represent the *model* rating in the
   baseline. FR-A1 does **not** silently redefine `run_rating`; instead the
   effective public signal at the decision boundary is derived so that a
   non-`APPROVED` actionable direction becomes the existing `REVIEW` sentinel
   (`tradingagents/agents/rating.py:30`). Blocked recommendations therefore cannot
   escape as an actionable BUY through public signals, reports, or the memory log
   rating tag, while `model_rating` remains available for audit.

### 5.3 Inputs

- Position sizing: use an explicit structured `target_position_weight` (projected
  post-trade single-stock portfolio weight, fraction in [0, 1]). Preserve
  `position_sizing` prose for compatibility. **Never infer approval from free
  text.** Missing/ambiguous/invalid weight or supporting portfolio data →
  `NEEDS_REVIEW`.
- Never substitute average purchase price for current market value.
- Sector concentration: a minimal structured **portfolio risk snapshot**
  (`portfolio_value`, `cash`, holdings with `market_value` and `sector`, and a
  `valuation_date`) supplied explicitly by the caller or through an additive local
  portfolio input contract. The snapshot must be internally consistent
  (`cash + Σ holdings.market_value == portfolio_value`) and its `valuation_date`
  consistent with the run.
- **Cash-funded long assumption (documented for v1):** the trade is funded from
  cash. For a target weight `w`:
  `projected_stock_value = w * portfolio_value`;
  `projected_sector_value = current_sector_value - current_stock_value +
  projected_stock_value`. A genuine BUY must increase the existing position and the
  additional purchase (`projected_stock_value - current_stock_value`) must be
  affordable from available cash. A "BUY" that would reduce or not increase the
  position, or that is unaffordable, is not approved.
- **Target sector when the stock is not held:** supplied explicitly on
  `target_position.sector`. It is never inferred from prose or fetched over the
  network. If absent and the stock is not already held, the sector rule is
  `UNKNOWN` → `NEEDS_REVIEW`.
- **Sector-cap scope:** the v1 cap applies to the **affected sector** of the
  target stock (the sector the trade changes). Applying the cap to *all* sectors
  is a broader interpretation; this is flagged for team confirmation (§10).

### 5.4 Supported trade scope

- Ordinary long BUY is the priority: stop-loss required; projected single-name
  exposure ≤ 10%; projected sector exposure ≤ 30%; require stop < entry < target;
  reward-to-risk ≥ 1.5; stock not blacklisted.
- HOLD never creates an actionable trade (`NO_TRADE`).
- SELL is treated as risk-reducing only when supported by explicit existing-position
  and trade data. Unsupported short initiation or ambiguous direction →
  `NEEDS_REVIEW`.
- HOLD/SELL exemption applicability is flagged for team confirmation; proposed
  tests are recorded separately rather than silently assumed.

### 5.5 Policy and audit

- Versioned policy, initially `fr-a1-v1`, stable `policy_hash`. Draft thresholds
  10% / 30% / 1.5.
- Deterministic, injectable blacklist policy; consistent ticker normalization
  (`tradingagents/dataflows/symbols.py`).
- Audit record includes per-rule outcomes, minimal structured input snapshot,
  verdict, policy version and hash, UTC timestamp, evaluation latency. No
  credentials, raw prompts, or unnecessary personal portfolio details.
- Core engine has no network, no file I/O, no LLM. Audit persistence is an
  integration-layer responsibility.

## 6. Human review corrections incorporated

1. Verdict must affect the effective recommendation; preserve model rating
   separately; use `REVIEW` semantics at the boundary; verify API and CLI; no
   bypass; a separate node is not itself the safety guarantee.
2. Structured `target_position_weight`; no free-text approval; missing/ambiguous →
   `NEEDS_REVIEW`.
3. Minimal structured portfolio risk snapshot; deterministic projected sector
   exposure; cash-funded long assumptions documented; no network/invention.
4. Long-BUY scope; HOLD vs SELL handling; applicability documented; INV-A1 not
   weakened; exemptions flagged.
5. Verdict semantics and precedence; `NO_TRADE`; complete per-rule results;
   separate violation vs evaluated IDs.
6. Versioned policy and hash; injectable blacklist; audit fields; core purity;
   persistence at integration layer.
7. FR-A2/FR-A3 not approved; block `NEEDS_REVIEW` from automatic execution;
   do not modify shared requirements registry; do not implement B/C/D/E.

## 7. Consequences

Positive:

- Deterministic, offline-testable safety gate with first-class audit.
- Clear separation of model rating from risk judgment and actionability.
- Fail-closed on missing evidence; no silent weakening of INV-A1.

Negative / costs:

- Requires retaining structured objects in state (additive; source files must add
  state keys and return the Pydantic objects alongside unchanged strings).
- Requires a structured portfolio risk snapshot contract (additive input surface).
- Bumping the graph layout marker in `_run_signature` invalidates older checkpoints
  (they restart fresh) — intentional and safer.
- Integration must cover both entry paths to avoid divergence.

Neutral:

- Rendered Markdown, memory log, and existing `final_rating`/`run_rating`
  semantics remain the **model** rating; the gate adds adjacent fields. The
  *effective public signal* is derived separately from `risk_verdict`, so blocked
  recommendations surface as `REVIEW` without redefining `run_rating` itself.

## 9. Compliance

- This is new implementation work; the inherited TradingAgents baseline is
  explicitly not counted as the team's contribution beyond the integration points
  documented above.
- Architecture decision and verification evidence are recorded before production
  implementation, per the course's safety-critical process.

## 10. Reopening conditions

Reopen this ADR if any of the following are established by test evidence:

- Deterministic projected sector exposure cannot be computed from available
  structured data offline, and the team declines the additive portfolio snapshot.
- The enforcement boundary proves unable to cover both API and CLI without a
  network or LLM dependency.
- Team confirmation changes HOLD/SELL applicability in a way that alters rule sets.
- Team confirmation changes the sector-cap scope (affected sector vs all sectors).
- Any change would weaken INV-A1 or an approved requirement.

## 11. Staged rollout: core first, integration later

To keep the safety-critical core reviewable and isolated, implementation is split.

### Stage 1 — independent risk engine (the only stage approved next)

Writes **only** new files under `tradingagents/risk_gate/` and their core tests.
Does **not** modify graph, agent, CLI, reporting, rating, memory, or checkpoint
code. Proposed production files:

- `tradingagents/risk_gate/__init__.py` (public exports)
- `tradingagents/risk_gate/models.py` (enums, rule result, evaluation, audit, inputs)
- `tradingagents/risk_gate/policy.py` (versioned `fr-a1-v1` policy + stable hash)
- `tradingagents/risk_gate/sizing.py` (projected-weight derivation/validation)
- `tradingagents/risk_gate/portfolio_snapshot.py` (consistency + projected exposure)
- `tradingagents/risk_gate/engine.py` (pure `evaluate_risk` implementing R1–R6)

Structural constraints for the core (verified by tests, not prose only):

- No network, no file I/O, no LLM, no LangGraph import in the core modules.
- Deterministic, pure: same inputs → same evaluation (timestamps/latency aside).
- `triggered_violation_ids` ⊂ `evaluated_rule_ids`; only `VIOLATED` in the former.
- Precedence `REJECTED > NEEDS_REVIEW > APPROVED`; no `APPROVED` for any
  non-increasive, unaffordable, inconsistent, or over-cap decision.
- Malformed numeric inputs (`NaN`/`inf`) cannot validate into an approved result.
- Every evaluation yields complete per-rule results and an audit record.

Core-only verification command:

```
pytest tests/risk_gate -q \
  --ignore=tests/risk_gate/test_integration_retention.py \
  --ignore=tests/risk_gate/test_decision_boundary.py
```

### Stage 2 — integration (separate review and approval)

Adds `tradingagents/risk_gate/node.py` and edits `state.py`, `trader.py`,
`portfolio_manager.py`, `setup.py`, and `trading_graph.py` (state keys, structured
retention, checkpoint marker, state-log fields). The API/CLI/checkpoint acceptance
tests (`test_integration_retention.py`, `test_decision_boundary.py`) belong to this
stage and are **not approved** for Stage 1; they must not be claimed as approved
until separately reviewed.

## 12. Pending team-confirmation decisions

Recorded here and mirrored in the test plan; production must not assume them.

- **D-scope-1 (sector cap scope):** affected sector only (v1 default) vs all sectors.
- **D-scope-2 (SELL/short):** criteria for treating a SELL as risk-reducing with
  explicit existing-position and trade data. Until confirmed, unsupported SELL and
  ambiguous direction are never `APPROVED`; HOLD is never `ACTIONABLE`.
- **D-scope-3 (HOLD rule exemptions):** whether `R4` is `NOT_APPLICABLE` for HOLD.
- **D-scope-4 (blacklist source):** injectable policy (v1 default) vs config; adding
  a config-driven source is FR-A3 scope and is not implemented here.
