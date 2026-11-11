# NFR-E1 — Reproducible Evaluation Harness (Team Handoff)

NFR-E1 builds an **offline, deterministic, auditable evaluation harness** for
TradingAgents: a fixed golden set of `(ticker, date)` cases, a per-run manifest,
repeat-run stability checks, and a before/after comparison table. It proves the
**harness and graph structure are deterministic under a fixed scripted source**;
it does **not** claim real-input reproducibility — that needs recorded replay
(FR-E4, out of scope here).

All work is on branch `feat/nfr-e1-eval`; baseline is `46bde74` (TradingAgents
v0.7.1).

Authoritative detail lives in the requirement/architecture docs — this README
only orients you:

- Registry entry: [`docs/req/requirements.yaml`](../../req/requirements.yaml) (NFR-E1 + nested FR-E1/FR-E2/FR-E3/INV-E1)
- Schema: [`docs/req/req-schema.json`](../../req/req-schema.json)
- Trace matrix: [`docs/architecture/trace-matrix.md`](../../architecture/trace-matrix.md)
- Invariants: [`docs/architecture/invariants.md`](../../architecture/invariants.md)
- ADR: [`docs/architecture/adr/001-eval-harness.md`](../../architecture/adr/001-eval-harness.md)
- Structure mapping: [`docs/architecture/repository-structure-mapping.md`](../../architecture/repository-structure-mapping.md)
- Verification capture: [`verification/README.md`](verification/README.md)
- Demo: [`demo/README.md`](demo/README.md)
- AI-use log: [`docs/ai-use-log.yaml`](../../ai-use-log.yaml)

## 1. Harness modules (`eval/`)

- `golden.py` — the fixed golden set (3 `(ticker, date)` cases).
- `sources.py` — `Source` / `LLMSource` protocols, `ScriptedSource`,
  `ScriptedLLMSource`, `EvalContext`; the shape is ready for recording/replay.
- `runner.py` — `run_case` (one case → rating + manifest), `run_suite` (isolated
  repeats; each run gets its own `run_id`, results dir, memory/state log).
- `manifest.py` — the per-run manifest; unavailable fields are `null` with a
  reason in `unavailable_sources` (never faked).
- `compare.py` — `compare(before, after)` writes `compare.csv` and `compare.md`.

## 2. What is proven vs not

- Proven: deterministic rating/report/token output under a fixed scripted
  source; per-run isolation; manifest completeness for available fields.
- Not proven: real-input reproducibility (FR-E4 recording/replay).
- Six gate scripts and the CI workflow are wired; PR #6 runs all nine checks
  green. Branch protection (9 checks + one review) is configured, and a real
  bad PR (#7) was blocked by gate-3.

## 3. Status

See the trace matrix for requirement-level status. FR-E1 is `implemented`;
FR-E2, FR-E3 and INV-E1 are `partial`.
