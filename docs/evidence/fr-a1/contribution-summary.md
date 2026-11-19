# FR-A1 Contribution Summary

Scope: FR-A1 — Deterministic Risk Gate (Owner A). Baseline upstream
TradingAgents v0.7.1 at team commit `46bde74`. All work below is on branch
`feat/fr-a1-risk-gate`.

Everything here is supported by repository history (`git log 46bde74..HEAD`) or by
the approvals recorded in this project's human-review dialogue. Timestamps beyond
commit dates are not invented.

## The seven FR-A1 commits

| # | Commit | Date | Type | Summary |
|---|---|---|---|---|
| 1 | `9631f78` | 2026-11-11 | test | Establish FR-A1 core specification and acceptance tests (ADR, test plan, full core test suite). |
| 2 | `2039ef1` | 2026-11-11 | feat | Implement initial FR-A1 deterministic risk engine (`tradingagents/risk_gate/` core modules). |
| 3 | `2981e3c` | 2026-11-11 | test | Reproduce three FR-A1 core safety defects via targeted RED tests. |
| 4 | `27c8b30` | 2026-11-11 | fix | Prevent FR-A1 rating, sector, and price validation bypasses. |
| 5 | `0bc9678` | 2026-11-11 | test | Establish FR-A1 system integration acceptance tests (ADR + test plan updates). |
| 6 | `2c3b226` | 2026-11-11 | test | Cover FR-A1 audit and trader-action safety (adapter safety tests + baseline contract migration). |
| 7 | `e716596` | 2026-11-11 | feat | Integrate FR-A1 risk gate into TradingAgents (Portfolio Manager boundary adapter + graph/state wiring). |

This ordering is strictly test-first: each `feat`/`fix` is preceded by a `test`
commit that encodes the target behaviour and fails RED before the implementation.

## Functional implementation and integration

New package `tradingagents/risk_gate/` (1,084 lines):

- `models.py` — structured inputs/outputs, verdict/status/outcome enums, audit types.
- `policy.py` — versioned `fr-a1-v1` policy with stable SHA-256 `policy_hash` and a
  normalized injectable blacklist.
- `sizing.py` — projected target-weight validation.
- `portfolio_snapshot.py` — snapshot consistency, valuation-date check, normalized
  sector handling, projected post-trade sector exposure.
- `engine.py` — pure `evaluate_risk`: R1 stop-loss, R2 single-name cap, R3 sector
  concentration, R4 direction-aware reward/risk, R5 blacklist, R6 input integrity;
  precedence `REJECTED > NEEDS_REVIEW > APPROVED`; `UNKNOWN` distinct from
  `VIOLATED`.
- `adapter.py` — `build_inputs`, `apply_gate` (single evaluation), `persist_audit`
  (durable writer), publication authorization (audit-before-publish).

Integration edits (minimal, additive): `agents/state.py` (structured + risk keys),
`agents/trader/trader.py` (retain `TraderProposal`), `agents/managers/portfolio_manager.py`
(retain `PortfolioDecision`, run the gate once at the output boundary),
`graph/trading_graph.py` (`risk_gate` checkpoint marker, audit in state log).

## Five confirmed safety defects / integrity gaps (RED → GREEN)

1. **Invalid/`REVIEW`/missing final model rating** could be substituted by the
   Trader's action → now R6 `UNKNOWN` (BUG-001, `27c8b30`).
2. **Sector-classification bypass** (case/whitespace/conflicting labels) could yield
   a false PASS → normalized sector keys + conflict detection (BUG-002, `27c8b30`).
3. **Non-positive prices** passing valid ordering and reward/risk → strict
   positivity required (BUG-003, `27c8b30`).
4. **ACTIONABLE without a durable audit destination** → downgrade/fail-closed
   (Stage 2 final review, `e716596`).
5. **Missing Trader action with a valid PM rating** recorded R6 PASS → now R6
   `UNKNOWN` (Stage 2 final review, `e716596`).

Each was encoded as a failing test before the fix (commits 3→4 and 6→7).

## Real human review and approval interventions (from the session record)

- Requirements classification and architecture candidates; approval of the
  pure-engine / pure-integration split.
- Test-plan approval with concrete fixture corrections (portfolio consistency,
  blacklist-must-analyze-the-ticker, directed 100-fixture generation).
- Explicit pre-implementation RED evidence required before any production code.
- Core safety-edge review that surfaced BUG-001..003.
- Stage 2 output-boundary architecture approval and CLI-config-path correction
  (Python API is the supported path; CLI fails closed).
- Audit-before-publication ADR revision and approval.
- Final approval of the two Stage 2 safety fixes (durable destination; missing
  Trader action).

Approvals were explicit, gate-by-gate; no production code was written before the
corresponding human approval.

## Test-first RED → GREEN evidence

- `2981e3c` adds `tests/risk_gate/test_core_safety_edges.py` which fails (RED) on
  the three bypasses; `27c8b30` makes it GREEN.
- `2c3b226` adds `tests/risk_gate/test_adapter_safety.py`; at that commit the
  durable-destination and missing-Trader-action tests are RED; `e716596` makes them
  GREEN.
- `0bc9678` establishes integration acceptances that are RED until `e716596`.

## Architecture revisions and rationale

- **Separate LangGraph node → Portfolio Manager output-boundary adapter.** Chosen
  after inspecting actual publication/streaming: a single evaluation at the PM
  boundary covers the `propagate` signal, state log, memory rating, reports, and CLI
  merge, avoiding a second evaluation surface.
- **Audit-before-publication ordering.** Derived from the streamed-audit-failure
  test: an actionable rating may not be released unless the durable audit is
  written.
- **Durable-destination enforcement.** Derived from the no-audit-dir RED test:
  missing destination downgrades to NEEDS_REVIEW rather than silently approving.

## Remaining team integration and policy decisions

- P1 HOLD applicability of R4; P2 SELL/short risk-reducing criteria; P6 sector-cap
  scope (affected sector vs all sectors); blacklist source (FR-A3 territory).
- Dependencies on Owners D (structured-output stability), E (manifest schema for
  `risk verdicts` / `policy_version`, CI gates), B/C (evidence, budget). FR-A2
  approval queue and FR-A3 configuration remain out of scope.

## Scale

`git diff --stat 46bde74..HEAD`: 34 files changed, 4,754 insertions, 20 deletions.
17 FR-A1 test modules under `tests/risk_gate/`.
