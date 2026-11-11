# FR-A1 Human Review & Approval Milestones

Recorded from the project's human-review dialogue and the repository history.
Only milestones that actually happened in the session are listed; no timestamps,
decisions, or approvals are invented.

Each milestone is a human gate that preceded repository changes. The commit that
records the resulting work is given where applicable.

## 1. Requirements and architecture

- Human set the mandatory supervised pipeline: classification → architecture
  candidates → decision/interfaces → test-plan approval → implementation approval →
  agent implementation → verification → revision on evidence.
- Human approved splitting a deterministic, pure **risk engine** from a thin
  **integration adapter**.
- Recorded in `9631f78` (ADR + test plan + core tests).

## 2. Core test specification

- Human required correcting test fixtures before implementation:
  internally consistent portfolio snapshots; blacklist fixtures must blacklist the
  **analyzed** ticker; 100 invalid fixtures with distinct, reproducible cases and
  expected rule outcomes (`VIOLATED` vs `UNKNOWN`).
- Human required that the suite fail RED before implementation (no stub code).
- Result: `9631f78` (tests only).

## 3. Core engine implementation approval

- Human explicitly authorised Stage 1 (engine only) with a fixed file-write scope.
- Result: `2039ef1` (engine), all core tests GREEN.

## 4. Core safety-edge review

- Human requested targeted regression tests for three suspected defects (invalid
  final rating; sector-classification bypass; non-positive prices) **before** any
  fix. Tests confirmed 10 failing / 3 passing.
- Human approved the fixes after reviewing the RED evidence and root causes.
- Result: `2981e3c` (RED tests) → `27c8b30` (fixes; GREEN).

## 5. Stage 2 integration design review

- Human approved the Portfolio Manager **output-boundary** architecture in
  principle but required corrections: no fabricated CLI config path; real
  audit-failure injection; audio-before-publication reasoning; actual legacy
  checkpoint behaviour; real adapter performance measurement.
- Human directed that the Python API is the supported `risk_portfolio` path and the
  default CLI must fail closed.
- Result: `0bc9678` and `2c3b226` (integration acceptance tests + adapter safety
  tests + baseline contract migration).

## 6. Final Stage 2 safety fixes approval

- Human approved exactly two targeted fixes (durable audit destination;
  missing-Trader-action → R6 UNKNOWN) after the test-first RED was recorded.
- Human accepted the intentional fail-closed baseline change (runs without
  `risk_portfolio` now surface `REVIEW`).
- Result: `e716596` (integration; safety tests GREEN).

## 7. Evidence packaging

- Human requested this evidence folder: reproducible demo, actual verification
  capture, contribution summary, and this milestone record; and explicitly required
  that no synthetic D5 transcript be fabricated.

## Notes on the nature of each gate

- Every production change was preceded by an approved, human-authored gate and a
  failing (RED) test that encodes the intended behaviour.
- The human, not the agent, decided scope boundaries (FR-A1 only; FR-A2/FR-A3
  deferred) and resolved ambiguities (CLI vs API config path; intentional `REVIEW`
  contract; durable-audit semantics).
