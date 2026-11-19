# FR-A1 Remaining Dependencies and Open Decisions

These items are recorded in the ADR (`docs/architecture/adr/adr-fr-a1-risk-gate.md`)
and test plan (`docs/req/fr-a1-test-plan.md`). They are **not** implemented and
require team confirmation or other owners' work.

## Policy decisions pending human/team confirmation

- **P1 — HOLD applicability of R4.** Proposed: `R4` is `NOT_APPLICABLE` for a HOLD;
  an approved HOLD is `NO_TRADE`, never `ACTIONABLE`. (See `test_trade_scope.py`;
  one proposal test is a documented non-strict xfail/xpass.)
- **P2 — SELL/short risk-reducing criteria.** Until confirmed, an unsupported
  SELL/short is never `APPROVED`. The exact criteria that would make a SELL a
  supported risk-reducing trade with explicit position/trade data are pending.
- **P6 — Sector-cap scope.** v1 applies the 30% cap to the **affected sector** of the
  target stock. Applying it to *all* sectors is a broader interpretation pending
  confirmation.
- **Blacklist source.** v1 uses an injectable policy constant; a config-driven source
  is FR-A3 scope.

## Cross-team integration dependencies

- **Owner D (structured adapter).** The gate consumes `TraderProposal` and
  `PortfolioDecision`. If D's structured-output path degrades or falls back to free
  text, the gate fails closed (NEEDS_REVIEW) — behaviour is safe, but approval then
  requires D's structured path to be healthy.
- **Owner E (eval harness / manifest / CI).** The gate writes `risk_verdict`,
  `decision_status`, `model_rating`, `policy_version`, `policy_hash`, and the
  redacted `risk_evaluation` into the state log. E's run manifest schema must include
  these (`risk verdicts`, `policy_version`) and the six blocking CI gates must cover
  the FR-A1 tests.
- **Owners B/C.** No hard dependency for FR-A1 correctness; evidence refs (B) and
  token budget (C) are independent features.

## Out of scope in this stage (deliberately deferred)

- **FR-A2 — human approval queue.** FR-A1 emits `NEEDS_REVIEW` and blocks automatic
  execution; the workflow that records a human approver/time/reason is FR-A2 and
  awaits separate scope approval.
- **FR-A3 — advanced configuration.** Runtime-reloadable thresholds are not
  implemented; the policy is code-defined and versioned (`fr-a1-v1`) with a stable
  hash.
- A documented CLI surface for supplying `risk_portfolio` (today the only supported
  path is the Python API `TradingAgentsGraph(config={"risk_portfolio": ...})`; the
  default CLI fails closed).

## Known limitations (documented, not defects)

- **Durability:** `persist_audit` writes and closes a JSON file but does not `fsync`;
  the guarantee is "written before publication", not crash/power-loss durability.
- **SELL/short in v1:** unsupported; never approved (safety), rather than
  implemented as a supported trade.
