# ADR-FR-A1: Deterministic Risk Gate

- Status: Implemented on the `feat/fr-a1-risk-gate` feature branch, pending team
  review and merge. (The test-first decisions below were made and approved before
  implementation and are preserved as the historical record.)
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

## 13. Stage 2 integration architecture (revised decision)

This section records the integration decision **before** integration coding. It
revises the Stage 2 description in §11 based on inspection of the actual
publication and streaming behavior in `46bde74`.

### 13.1 Where a recommendation is published

Every consumer derives the *effective* public signal from
`run_rating(final_state)` (which reads `final_rating`):

- `TradingAgentsGraph._run_graph` returns `run_rating(final_state)` as the signal.
- `_log_state` writes `final_rating` into the state log.
- `record_decision` writes the memory-log rating tag.
- `reporting._header` writes `- Rating: …`; `report_html` renders it as a badge.
- The CLI's post-run notice uses `is_review(run_rating(final_state))`.

Graph streaming (`stream_run`) emits per-node deltas; the Portfolio Manager is the
last node and `record_decision` is called only after the stream ends.

### 13.2 Selected boundary: Portfolio Manager output adapter (not a separate node)

The gate is invoked **once**, inside the Portfolio Manager node, at its output
boundary, because that node is the single point where both structured objects exist
and after which *every* publication path consumes `final_rating`. A separate graph
node would add a second evaluation surface and require every consumer path to be
audited again; the PM boundary is the smallest single authoritative decision
boundary and covers API and CLI-merge identically.

The adapter:
- retains `trader_proposal` and `portfolio_decision` in state (structured, no
  Markdown re-parsing);
- builds `RiskInputs` from the structured objects plus a caller-supplied
  `PortfolioRiskSnapshot`/`TargetPosition`;
- runs `evaluate_risk(policy)` exactly once;
- preserves the model rating in `model_rating` and writes `final_rating` =
  effective public signal (`REVIEW` when `risk_verdict != APPROVED`, else the model
  rating), plus `risk_verdict`, `decision_status`, `risk_evaluation`;
- persists the audit record into the state log (append-only) without changing the
  rendered strings consumers already read.

This is a **revision** of §11's "adds `node.py`" — the boundary adapter replaces the
separate node for v1, keeping one evaluation.

### 13.3 Input availability (additive, caller-facing)

A new additive config key `risk_portfolio` (a dict matching
`PortfolioRiskSnapshot` + optional `target_position`) supplies the structured
snapshot and target weight. It is passed through `config` to the adapter so both
`propagate()` and the CLI can supply it. When absent, inputs are incomplete and
the gate fails closed (NEEDS_REVIEW), never approving on missing data. The adapter
never parses Markdown sizing nor invents market values/prices/sectors. The
reachable APPROVED path for an in-bounds BUY is exercised offline by supplying the
snapshot; this prevents "everything is NEEDS_REVIEW" by construction.

Both structured decisions are required: a missing/invalid Trader `action` **and** a
missing/invalid final `PortfolioDecision.rating` each make R6 UNKNOWN (already
implemented for the rating; the adapter must also treat a missing action as
incomplete rather than letting the rating alone define direction silently).

### 13.4 Exact files and interfaces affected (Stage 2 coding, later)

- `tradingagents/agents/state.py` — additive keys: `trader_proposal`,
  `portfolio_decision`, `model_rating`, `risk_verdict`, `decision_status`,
  `risk_evaluation`.
- `tradingagents/agents/trader/trader.py` — return `trader_proposal` alongside the
  unchanged rendered string.
- `tradingagents/agents/managers/portfolio_manager.py` — return
  `portfolio_decision`; invoke the gate adapter; set `final_rating` to the
  effective signal only through the adapter.
- `tradingagents/graph/trading_graph.py` — pass `risk_portfolio` config to the PM
  adapter; add a `risk_gate` layout marker to `_run_signature`; persist the audit
  record in `_log_state`; guard `record_decision` so an audit-persistence failure
  cannot leave an actionable signal.
- `tradingagents/risk_gate/adapter.py` (new) — pure wiring from structured objects
  + snapshot to `RiskInputs`, and the gate call. No graph import in the engine.

No changes to `rating.py`, `reporting.py`, `report_html.py`, `cli/*`,
`memory/*`, or `checkpoint.py` semantics are required: they consume `final_rating`,
which the adapter sets to the effective signal, and `model_rating` is preserved for
evidence.

### 13.5 Safe pre-gate checkpoint behavior

The `risk_gate` marker in `_run_signature` changes the thread id, so a checkpoint
saved before the gate cannot resume into a gated graph; it starts fresh and is
evaluated. This is the behavior the checkpoint test asserts (actual resume, not a
hash substring).

### 13.6 Intentional behavior changes vs regressions

Intentional (safety): `final_rating` (and therefore the propagate signal, state
log `final_rating`, memory rating tag, report rating header, HTML badge, and CLI
notice) becomes `REVIEW` for REJECTED/NEEDS_REVIEW while `model_rating` retains the
model's own value. Rendered decision text is unchanged. Everything else is a
regression if it changes.

## 14. Stage 2 revision: audit-before-publish (from final test review)

The output-boundary adapter (§13.2) computes the verdict before the PM node returns,
so no consumer can see an actionable BUY that was not evaluated. The final review
identified a narrower gap: **on-disk audit durability relative to publication**.

### 14.1 Decision

The gate must establish the durable audit **before** an actionable (`APPROVED`)
signal is released. Two facts constrain this:

- The state log is written by `record_decision` *after* the stream ends; the PM
  node return (and any streamed `final_rating`) precedes it.
- A streamed `final_rating == "Buy"` could therefore be observed before the audit
  is on disk if persistence happened only in `record_decision`.

To guarantee safety without adding a second evaluation:

1. The adapter computes the verdict (once) and, for `APPROVED` only, **persists the
   audit record durably before returning** the state update that sets
   `final_rating` to an actionable rating. For `REJECTED`/`NEEDS_REVIEW` the
   published value is `REVIEW`, which is already non-actionable, so persistence may
   occur either before or alongside `_log_state`; the recommendation cannot be
   acted on regardless.
2. `_log_state` also records the audit (append-only) for the run manifest.
3. If durable persistence raises, the adapter **fails closed**: it does not emit an
   actionable `final_rating`; the run surfaces the failure (or downgrades to
   `REVIEW` with the failure recorded) rather than approving.

This keeps a single evaluation and one authoritative boundary. It is a refinement
of §13.2, not a new architecture.

### 14.2 Audit content (minimum necessary)

The persisted audit is the `RiskEvaluation`: rule ids + outcomes, the minimal
`input_snapshot` (including `target_position_weight`, `portfolio_value`, `cash`,
`target_sector`, prices, action, model rating), derived per-rule `observed`/
`threshold` values (so R2 weight and R3 projected sector exposure are explainable),
verdict, `decision_status`, `policy_version`, `policy_hash`, `evaluated_at_utc`,
and `latency_ms`. No credentials, prompts, or full holdings beyond what explains
the two exposure rules.

### 14.3 Consequence for tests

- The streamed-output test must show no actionable BUY is released without a
  durable audit; a simulated persistence failure must not yield an actionable
  `final_rating` on the stream. The failure is injected by patching the **actual**
  durable writer (`tradingagents.risk_gate.adapter.persist_audit`) with
  `raising=True`, recording that it was invoked, so a missing writer fails the test
  RED rather than silently injecting an unused fake.
- The audit must contain the numeric inputs and derived exposures for R2/R3.

### 14.4 Caller configuration path (documented, not invented)

There is **no** `risk_portfolio` CLI flag or environment variable, and this stage
adds none. The only supported caller path for valid inputs is the **Python API**:
`TradingAgentsGraph(config={"risk_portfolio": {...}})` (exercised by the Python-API
test). The **default CLI path** supplies no structured snapshot and therefore
**fails closed** to `NEEDS_REVIEW` → `REVIEW`. Any future CLI surface would be a
separate, explicitly-approved change; no test claims a CLI feature that does not
exist.

The durable audit writer is defined by the Stage 2 adapter as
`tradingagents.risk_gate.adapter.persist_audit(evaluation, ...)`; it must be called
for **every** evaluation before the Portfolio Manager publishes an actionable
recommendation.

## 15. Stage 2 final safety review: durable destination, missing action, malformed inputs

Source review of the Stage 2 implementation found three gaps; this section records
the required contract (verified test-first in `tests/risk_gate/test_adapter_safety.py`).

### 15.1 Durable audit destination is mandatory for ACTIONABLE output

`persist_audit(evaluation, audit_dir=None)` returning an in-memory payload is **not**
a durable audit. The approved contract (extends §14):

- An `APPROVED`/`ACTIONABLE` recommendation may be published **only** if a real
  durable audit record was written to disk before publication.
- A missing (`None`) or unusable audit destination must **not** silently bypass
  persistence: the decision must not be `ACTIONABLE` (fail closed by raising is
  acceptable).
- The rule applies to **every** evaluated decision, not just rejected ones; an
  `APPROVED` decision must have an actual persisted audit file.

Consequence: `apply_gate` must treat the audit destination as required for an
actionable result — either the caller supplies a writable `audit_dir`, or the
result is not actionable. The PM boundary always supplies the run's
`results_dir/<ticker>/risk_audit`.

### 15.2 A valid PortfolioDecision rating does not substitute for a missing Trader action

When `trader_proposal` is `None` (or its action is missing/invalid), a valid PM
rating must **not** supply the trade direction on its own:

- The result must not be `APPROVED` or `ACTIONABLE`.
- R6 input integrity must record the uncertainty (UNKNOWN), not PASS.
- The model rating remains available in `model_rating` as evidence.

This refines the R6 semantics in §5.2 and the adapter contract in §13.3: an
unusable Trader action is an input-integrity gap even when the PM rating is valid.

### 15.3 Malformed `risk_portfolio` handling

Caller inputs are never trusted or invented. For non-dict `risk_portfolio`, invalid
snapshot schema/numeric fields, or malformed `target_position`:

- Prefer an auditable `NEEDS_REVIEW` when a safe evaluation can be constructed.
- An explicit fail-closed exception is acceptable where safe evaluation or audit
  persistence is impossible.
- The result must **never** be `ACTIONABLE`.

### 15.4 Baseline contract migration (approved)

The six `tests/test_graph_end_to_end.py` assertions that expected the old model
rating (`Overweight`) for runs **without** `risk_portfolio` are migrated to the
approved fail-closed effective signal `REVIEW`. Unrelated assertions (graph
completion, checkpoint recovery, state logs, memory, rendered decisions, agent
execution) are preserved; where structured data exists the original model rating is
verified separately via `model_rating`. This is an intentional, human-approved
behavior change, not a regression.

### 15.5 Implementation status

The durable-destination rule (§15.1) and the missing-action R6 rule (§15.2) were
implemented in commit `e716596`; their tests in `test_adapter_safety.py` now pass
(RED → GREEN). This section remains as the recorded test-first contract.

## 16. Audit semantics: rule verdict vs publication authorization

This section records (without changing runtime semantics) the distinction the
implementation already draws, so audit readers are not misled.

- **`risk_evaluation.verdict` is the core rule outcome.** It is the policy verdict
  computed by the rules (R1–R6) over the supplied inputs, independent of any sink.
- **`risk_verdict` is the effective publication outcome.** It is what the adapter
  returns as the decision that may be published, and it can differ from the core
  rule outcome.
- **APPROVED core rules do not authorize publication when the required audit has
  not been persisted.** Publication of an actionable recommendation additionally
  requires a successful durable audit write. `apply_gate` therefore downgrades an
  otherwise-APPROVED, ACTIONABLE decision.
- **`audit_dir=None` produces a non-actionable downgrade.** When the adapter would
  publish an ACTIONABLE recommendation but no audit destination is supplied, it
  returns `risk_verdict = NEEDS_REVIEW`, `decision_status = PENDING_REVIEW`, and
  `final_rating = REVIEW` instead. In that case `risk_evaluation.verdict` may still
  read `APPROVED` — this is the rule outcome, not the publication outcome. A durable
  audit failure with a provided destination raises a fail-closed error instead.
- **File write and close do not imply fsync-level crash durability.** `persist_audit`
  writes and closes a JSON file; it does not `fsync`. The guarantee is that the
  record was written before publication, not that it survives a power loss.

Consequence for audit consumers and the persisted state log: read `risk_verdict` /
`decision_status` / `final_rating` for what was published, and `risk_evaluation` for
why the rules reached their outcome. When these disagree, the disagreement is the
audit/authorization gate, not a data error.
