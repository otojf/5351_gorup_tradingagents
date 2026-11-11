# FR-A1 Test Plan — Deterministic Risk Gate

- Status: Authoring approved; production implementation blocked pending review of these tests.
- Date: 2026-11-11
- Owner: A
- Requirement: FR-A1, with INV-A1, NFR-A1, NFR-A2
- Related ADR: `docs/architecture/adr/adr-fr-a1-risk-gate.md`
- Baseline: `46bde74`

This plan describes the agreed contract and its offline test coverage. It is
written before production implementation so the tests can be reviewed. Tests
reference the requirement/invariant they enforce. Intentional safety-related
behavior changes are marked `[SAFETY]`; everything else must remain an existing
behavior (`[PRESERVE]`).

## 1. Proposed interface (contract under review)

The tests are written against this interface. It is expected to match the
eventual implementation; production code is not written yet.

### 1.1 Package `tradingagents.risk_gate`

Modules (proposed): `models.py`, `policy.py`, `engine.py`, `sizing.py`,
`portfolio_snapshot.py`, `node.py` (integration). The core engine modules have no
network, no file I/O, no LLM imports.

### 1.2 Enumerations

```python
class RiskVerdict(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class DecisionStatus(StrEnum):
    ACTIONABLE = "ACTIONABLE"
    BLOCKED = "BLOCKED"
    PENDING_REVIEW = "PENDING_REVIEW"
    NO_TRADE = "NO_TRADE"

class RuleOutcome(StrEnum):
    PASS = "PASS"
    VIOLATED = "VIOLATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
```

### 1.3 Rule identifiers

| ID | Meaning |
|---|---|
| `R1_STOP_LOSS_REQUIRED` | Long actionable BUY must carry a stop-loss |
| `R2_SINGLE_NAME_CAP` | Projected single-name weight ≤ 10% (0.10) |
| `R3_SECTOR_CONCENTRATION` | Projected sector exposure ≤ 30% (0.30) |
| `R4_REWARD_RISK` | Direction-aware reward-to-risk ≥ 1.5 and ordering stop<entry<target |
| `R5_BLACKLIST` | Ticker not on the deterministic blacklist |
| `R6_INPUT_INTEGRITY` | Structured inputs present, consistent, unambiguous |
| `R0_ALL_RULES_PASSED` | Positive marker so every verdict carries a rule ID |

`R0` is a synthetic "pass" entry: every evaluation carries at least one rule ID,
satisfying "100% of verdicts carry a rule identifier" (`requirements.yaml:28`),
including clean approvals.

### 1.4 Input models

```python
class TargetPosition(BaseModel):
    target_position_weight: float | None   # projected post-trade single-name weight, 0..1
    sector: str | None = None               # target stock's sector, required when not held

class Holding(BaseModel):
    ticker: str
    market_value: float          # current market value; never average cost
    sector: str | None

class PortfolioRiskSnapshot(BaseModel):
    valuation_date: str          # ISO date; must be consistent with the run's trade_date
    portfolio_value: float       # total portfolio value used for weight denominators
    cash: float                  # cash available to fund a cash-funded long
    holdings: list[Holding]
    # consistency: cash + Σ holdings.market_value == portfolio_value

class RiskInputs(BaseModel):
    ticker: str
    trade_date: str
    action: str | None           # TraderProposal.action, if structured output produced it
    entry_price: float | None
    stop_loss: float | None
    price_target: float | None   # PortfolioDecision.price_target
    model_rating: str | None     # PortfolioDecision.rating, verbatim
    target_position: TargetPosition | None
    portfolio: PortfolioRiskSnapshot | None
```

**Projected exposure (cash-funded long, documented for v1):**
`projected_stock_value = target_position_weight * portfolio_value`;
`projected_sector_value = current_sector_value - current_stock_value +
projected_stock_value`. A genuine BUY increases the position and the purchase
(`projected_stock_value - current_stock_value`) is affordable from `cash`. Missing
target sector for an unheld stock, or an inconsistent snapshot, makes the affected
rule `UNKNOWN` → `NEEDS_REVIEW`, never `APPROVED`.

### 1.5 Output models

```python
class RuleResult(BaseModel):
    rule_id: str
    outcome: RuleOutcome
    detail: str                      # deterministic; no PII/credentials
    observed: float | None = None
    threshold: float | None = None

class RiskEvaluation(BaseModel):
    verdict: RiskVerdict
    decision_status: DecisionStatus
    model_rating: str | None
    evaluated_rule_ids: list[str]        # every rule considered
    triggered_violation_ids: list[str]   # only VIOLATED rule ids
    rule_results: list[RuleResult]       # complete per-rule results
    policy_version: str
    policy_hash: str
    input_snapshot: dict                 # minimal, redacted snapshot
    evaluated_at_utc: str                # ISO8601 UTC
    latency_ms: float

class RiskAuditRecord(BaseModel):
    audit_id: str
    evaluation: RiskEvaluation
```

### 1.6 Engine entry points

```python
def evaluate_risk(inputs: RiskInputs, policy: RiskPolicy | None = None) -> RiskEvaluation: ...

class RiskPolicy:
    version: str          # "fr-a1-v1"
    policy_hash: str      # stable hash of the constants
    single_name_cap: float = 0.10
    sector_cap: float = 0.30
    min_reward_risk: float = 1.5
    blacklist: frozenset[str] = frozenset()
```

`evaluate_risk` is pure and deterministic. Ticker normalization uses
`tradingagents.dataflows.symbols.normalize_symbol`.

## 2. Rule semantics and applicability

Precedence for the final verdict: `REJECTED > NEEDS_REVIEW > APPROVED`.

**UNKNOWN is not VIOLATED.** `triggered_violation_ids` lists only rules whose
outcome is `VIOLATED`; `evaluated_rule_ids` lists every rule considered. When a
rule cannot be decided for lack of input it is `UNKNOWN` (→ `NEEDS_REVIEW`), not a
violation. Example: a missing stop-loss makes `R1` `VIOLATED` while `R4` is
`UNKNOWN` (the ratio cannot be computed).

**Three separate concepts at the boundary:** `model_rating` (the PM's own rating,
preserved), `risk_verdict` (from the gate), and the *effective public signal*
(a non-`APPROVED` actionable direction surfaces as the existing `REVIEW`
sentinel). `final_rating`/`run_rating` keep their baseline meaning — the **model**
rating — and are not redefined; the gate produces the effective public signal
separately so blocked recommendations cannot escape as an actionable BUY.

| Rule | Applies when | Violated → | Unknown/inapplicable → |
|---|---|---|---|
| R1 stop-loss | long actionable BUY (action Buy) | REJECTED | — |
| R2 single-name | BUY with a resolvable weight | REJECTED (>0.10) | NEEDS_REVIEW (R2 UNKNOWN: missing weight) |
| R3 sector | BUY with a resolvable snapshot | REJECTED (>0.30) | NEEDS_REVIEW (R3 UNKNOWN: unknown sector/value) |
| R4 reward-risk | BUY with entry/stop/target | REJECTED (ratio<1.5 or bad ordering) | NEEDS_REVIEW (R4 UNKNOWN: missing leg) |
| R5 blacklist | any ticker | REJECTED (on list) | — (list always known) |
| R6 input integrity | always | — | NEEDS_REVIEW (R6 UNKNOWN: missing/contradictory/inconsistent) |

BUY: all of R1–R5 apply. HOLD: no actionable trade; approved HOLD → `NO_TRADE`
(R4 `NOT_APPLICABLE` is a pending decision). SELL/short without explicit
existing-position and trade data → not `APPROVED` (mandatory); exact risk-reducing
criteria are pending team confirmation. The sector cap applies to the **affected
sector** of the target stock in v1 (scope pending confirmation).

**As-implemented rule ownership (no semantic change, just allocation):**
- R2 checks the weight cap and the *genuine increase* clause (UNKNOWN when the
  buy does not increase the position).
- R3 checks projected affected-sector exposure (UNKNOWN when a holding lacks a
  sector, or the target sector is unknown).
- R6 checks input integrity that spans rules: contradictory/ambiguous direction,
  non-finite decision prices, an inconsistent or stale portfolio snapshot, and an
  unaffordable cash-funded purchase. In v1, an unsupported short/SELL is recorded
  by R6 as UNKNOWN (pending team confirmation), so it cannot be approved.
- Decision numeric fields are representable as `inf`/`nan` at the model layer so a
  malformed value degrades to UNKNOWN (NEEDS_REVIEW); it can never become a usable
  number or an approval.

## 3. Requirement traceability

| Requirement | Contract element | Test file |
|---|---|---|
| FR-A1 verdict + rule IDs | `evaluate_risk`, `rule_results` | `test_rules.py`, `test_verdict_semantics.py` |
| FR-A1 5 injected violations 5/5 blocked | R1–R5 fixtures | `test_rule_violations.py` |
| FR-A1 100 invalid fixtures 0 approvals | fixture generator | `test_100_invalid_fixtures.py` |
| INV-A1 no approval without stop / over cap | invariants | `test_invariants.py` |
| NFR-A1 p95 ≤ 2 s, 0 network | pure engine + runtime/structural guard | `test_latency_no_network.py` |
| NFR-A2 audit completeness | `RiskAuditRecord` | `test_audit_trail.py` |
| §5.1 verdict affects recommendation | boundary enforcement | `test_decision_boundary.py` |
| §5.2 NO_TRADE for approved HOLD | `DecisionStatus` | `test_verdict_semantics.py` |
| §5.3 structured weight/snapshot | `TargetPosition`, `PortfolioRiskSnapshot` | `test_input_contract.py` |
| §5.4 trade scope | applicability | `test_trade_scope.py` |
| §5.5 policy version/hash | `RiskPolicy` | `test_policy_versioning.py` |
| Structured retention (API+CLI) | state keys | `test_integration_retention.py` |

## 4. Test matrix

All tests are `@pytest.mark.unit`, offline (the repo's `conftest.py` already
blocks sockets), parameterized deterministically. Files live under `tests/risk_gate/`.

### 4.1 Rule-level (`test_rules.py`)

- R1: BUY missing stop → REJECTED, id `R1_STOP_LOSS_REQUIRED`.
- R2: weight 0.12 → REJECTED; weight 0.10 → PASS; weight 0.099 → PASS.
- R3: sector 0.35 → REJECTED; 0.30 → PASS.
- R4: long RR 2.0 → PASS; RR 0.5 → REJECTED; short direction-aware.
- R5: blacklisted ticker → REJECTED; normalization for `aapl`/`AAPL`.
- Valid BUY (all in bounds) → APPROVED, `R0_ALL_RULES_PASSED` present.
- Wrong-side stop (long stop ≥ entry) → REJECTED; wrong-side target → REJECTED.

### 4.2 Exact boundaries (`test_boundaries.py`)

- 10% weight: `0.10` PASS, next representable above → REJECTED. The fixture holds a
  positive AAPL position, so a target weight of `0.0` (and a target equal to the
  held value) is **not approved** — a genuine BUY must increase the position.
- 30% **projected post-trade** sector: `0.30` PASS (inclusive), just over REJECTED.
- 1.5 RR: exactly `1.5` PASS; `1.4999...` REJECTED.

### 4.3 Injected violations (`test_rule_violations.py`)

Five individually isolated fixtures, each asserting the expected rule id is
`VIOLATED` and verdict `REJECTED`, with the *other* rules not violated: missing
stop (R1; R4 may be UNKNOWN), single-name 12% (R2), projected sector 40% (R3),
RR 0.5 (R4), blacklist (R5).

### 4.4 Malformed / missing inputs (`test_input_contract.py`)

- Missing target position/weight → NEEDS_REVIEW, R2 `UNKNOWN`, PENDING_REVIEW.
- Missing portfolio/sector → NEEDS_REVIEW, R3 `UNKNOWN`.
- Missing target price → NEEDS_REVIEW, R4 `UNKNOWN`.
- NaN/inf prices → NEEDS_REVIEW, never ACTIONABLE.
- Contradictory proposal/decision direction → NEEDS_REVIEW (R6 `UNKNOWN`).
- Inconsistent snapshot (holdings+cash ≠ portfolio_value), stale valuation date,
  unaffordable purchase → NEEDS_REVIEW, never ACTIONABLE.

### 4.5 Verdict semantics (`test_verdict_semantics.py`)

- Precedence REJECTED > NEEDS_REVIEW > APPROVED.
- All applicable rules collected (no first-fail).
- UNKNOWN is distinct from VIOLATED; `triggered_violation_ids` lists only VIOLATED.
- `triggered_violation_ids` ⊆ `evaluated_rule_ids`; both present for clean runs.
- Approved HOLD → `NO_TRADE`; approved BUY → `ACTIONABLE`; rejected → `BLOCKED`;
  needs-review → `PENDING_REVIEW`; model rating preserved on reject.

### 4.6 Trade scope (`test_trade_scope.py`)

Mandatory (hard assertions, not xfail): HOLD never ACTIONABLE; SELL/short without
explicit position+trade data never APPROVED; ambiguous direction never APPROVED.
A `test_proposed_*` records the pending SELL-with-data expectation separately.

### 4.7 Invariants (`test_invariants.py`)

- APPROVED ⇒ stop-loss present for actionable BUY.
- APPROVED ⇒ weight ≤ 0.10.
- APPROVED ⇒ decision_status in {ACTIONABLE, NO_TRADE}.
- Sweep over deterministic grid: no APPROVED violates INV-A1.

### 4.8 100 invalid fixtures (`test_100_invalid_fixtures.py`)

Simple, independent, reproducible parameterized cases (no fragile dictionary-
merging cross-products that could overwrite `target_position` or other inputs).
Exactly 100 **distinct** fixtures are exercised; distinctness is keyed on the
actual input payload and the policy (blacklist), excluding the case label.

Cases span **all five rules plus input-integrity failures** (R1–R6). Every
blacklist fixture explicitly blacklists the analyzed ticker (AAPL), so R5 applies.
Each case declares the rule it targets and the outcome that rule must record:

- `VIOLATED` cases assert the expected rule id is present with `VIOLATED` and is in
  `triggered_violation_ids`.
- `UNKNOWN` (input-integrity) cases assert the referenced rule is `UNKNOWN` and is
  **not** falsely recorded as `VIOLATED`.
- Aggregate: **0 of 100 APPROVED**, none ACTIONABLE; all of R1–R5 plus an
  input-integrity `UNKNOWN` outcome are represented; the 100 are distinct.
- A dedicated test asserts every blacklist fixture includes the analyzed ticker.

The affordability fixture uses a consistent 1,000,000 book (cash 10,000, AAPL
20,000, MSFT 150,000, others 820,000 across several non-Technology sectors); target
weight 0.05 → projected AAPL 50,000 (+30,000 increase) but only 10,000 cash, so R2
(0.05 ≤ 0.10) and R3 (Technology 20%) pass and affordability is the only blocker,
yielding `NEEDS_REVIEW` under the `REJECTED > NEEDS_REVIEW > APPROVED` precedence.

### 4.9 Audit (`test_audit_trail.py`)

- Required *values* verified (policy hash length, UTC timestamp format, latency,
  snapshot non-empty and value-bearing), not mere key presence.
- 10 evaluations → 100% audit coverage with identical version/hash.
- No credentials or raw prompt fields.

### 4.10 Policy versioning (`test_policy_versioning.py`)

- `version == "fr-a1-v1"`; `policy_hash` stable; distinct hash when a threshold
  changes; version/hash recorded in evaluation.

### 4.11 Latency / no network (`test_latency_no_network.py`)

- 1000 evaluations; measured **core** p95 ≤ 2000 ms; the measured p50/p95 is
  reported in the test output. Core latency is distinguished from integration
  overhead (graph wiring is covered separately).
- A runtime socket guard (every connect/`getaddrinfo` refuses) is installed for the
  evaluation loop; a subprocess structural check asserts importing the engine
  alone pulls in no network/LLM module.

### 4.12 Integration acceptance (`test_integration_retention.py`, `test_decision_boundary.py`)

**These are NOT approved for the core stage.** They are retained for the later
integration stage and will require separate review and approval before integration.
They exercise graph/CLI/checkpoint code and are expected to fail (RED) until that
stage. `[SAFETY]`/`[PRESERVE]` marked, real graph/CLI behavioral tests (not
existence checks).

- Programmatic API: **unconditional** assertions for REJECTED and for NEEDS_REVIEW —
  expected `risk_verdict`, effective public signal `REVIEW`, preserved
  `model_rating`, and `decision_status` (`BLOCKED`/`PENDING_REVIEW`).
- CLI stream path: a real `run_analysis` drive with a scripted streamed REJECTED
  BUY verifies the decision recorded downstream is not an actionable BUY
  (effective signal `REVIEW`, `decision_status` BLOCKED, `model_rating` kept).
- Structured objects retained in state without Markdown parsing (`[SAFETY]`).
- Audit persistence: state log records `risk_verdict` and `policy_version`
  (`[SAFETY]`).
- Checkpoint safety: the run signature carries a `risk_gate` **marker**, and a
  pre-gate checkpoint cannot resume into a gated graph — asserted structurally on
  the marker list, not by searching a hash for a word (`[SAFETY]`).
- Existing rendered strings and `run_rating` (model rating) unchanged (`[PRESERVE]`).

## 5. Expected outcomes before implementation

Because production code is absent, the risk-gate tests import the engine at test
execution time and fail (RED) with `ModuleNotFoundError: tradingagents.risk_gate`.
There is **no module-level importorskip and no production stub**. Test files are
collected before implementation; individual tests fail for real, proving they
exercise the gate. Collection succeeds; failures are the honest pre-implementation
state, never counted as passes. The existing regression suite must be unaffected
(`[PRESERVE]`).

## 6. Intentional safety changes vs regression

- `[SAFETY]` items intentionally change observable behavior at the decision
  boundary (non-APPROVED directions become `REVIEW`/blocked). These are not
  regressions.
- `[PRESERVE]` items must remain identical; failing ones indicate unintended
  regression and must not be "fixed" by weakening assertions.

## 7. Pending scope decisions (recorded separately)

Mandatory safety behavior is encoded as hard assertions, not non-strict xfail.
Genuinely unresolved policy extensions are recorded as `test_proposed_*` or here:

- P1 HOLD applicability of R4 (proposed: `NOT_APPLICABLE`).
- P2 SELL risk-reducing criteria and required explicit data (mandatory:
  unsupported SELL never approved).
- P3 Blacklist source (proposed: injectable policy).
- P4 FR-A2 boundary: NEEDS_REVIEW blocked from automatic execution.
- P5 Sector snapshot additive contract details.
- P6 Sector-cap scope: affected sector (v1 default) vs all sectors.

## 8. Staged implementation: core vs integration

Stage 1 (next, on approval) implements **only the independent risk engine** under
`tradingagents/risk_gate/` (pure, no network/file-I/O/LLM) and its **core** tests.
It does **not** modify graph, agent, CLI, reporting, rating, memory, or checkpoint
code. The core-only test command is:

```
pytest tests/risk_gate -q \
  --ignore=tests/risk_gate/test_integration_retention.py \
  --ignore=tests/risk_gate/test_decision_boundary.py
```

Stage 2 (later, separate approval) performs integration and the API/CLI/checkpoint
acceptance tests (`test_integration_retention.py`, `test_decision_boundary.py`).
Those tests are **not approved** for the core stage and must not be claimed as
such. Proposed core-stage production files are enumerated in the ADR.
