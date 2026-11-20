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
  reason in `unavailable_sources` (never faked). `prompt_hash` is a real sha256
  of the prompt-template source; `prompt_source_id` is the source label.
- `manifest_rules.py` — the draft interface for the A/B/D-owned manifest fields
  (degradations / risk verdicts / traceability): field shapes plus a normalizer.
- `compare.py` — `compare(before, after)` writes `compare.csv` and `compare.md`.

## 2. What is proven vs not

- Proven: deterministic rating/report output under a fixed scripted source; token
  fluctuation across repeats `<= 5%` (0 under the script); **0 network calls**
  during a run (socket/urlopen patched to fail); offline run `<= 10 minutes`;
  per-run isolation; manifest completeness for available fields.
- Proven as a seam only: the A/B/D fields accept well-formed injected data and
  reject malformed data (`test_manifest_records_injected_integration_data`). No
  real A1/B2/D2 producer is wired yet.
- Not proven: real-input reproducibility (FR-E4 recording/replay); latency is not
  asserted to a 5% band (wall-clock noise would make it flaky).
- Six gate scripts and the CI workflow are wired; PR #6 runs all nine checks
  green. Branch protection (9 checks + one review) is configured. **Only gate-3
  has live bad-PR evidence** (real bad PR #7 was blocked by the schema gate); the
  other five gates have local negative unit tests only — no live bad PR.

## 3. Status

See the trace matrix for requirement-level status. FR-E1 is `implemented`;
FR-E2, FR-E3 and INV-E1 are `partial`.
