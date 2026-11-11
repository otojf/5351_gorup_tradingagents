# CS5351 Project Report — TradingAgents

> STATUS: SKELETON. This file is a scaffold for the process report (D6). Sections
> marked TODO must be written by the team; nothing here invents contributions,
> reflections, or metrics. Target: ≤10,000 words (excluding diagrams) and >15
> pages at 12pt single spacing.

## 0. Team and relative contribution

Fill the table with actual productive hours (or story points) per sprint. The
average contribution is 1.0; individual weights are each member's hours / mean
hours (see the course's example). **Do not pre-fill numbers.**

| Member (name, student ID) | S1 | S2 | S3 | S4 | S5 | Total | Contribution = total / mean |
|---|---|---|---|---|---|---|---|
| TODO | | | | | | | |
| TODO | | | | | | | |
| TODO | | | | | | | |

Mean contribution = (sum of totals) / (number of members). TODO.

## 1. Introduction and purpose

TradingAgents is a multi-agent LLM system that produces a five-tier investment
rating for a ticker on a trade date. TODO: one paragraph on the team's goals and
the problem the project addresses.

## 2. Requirements process

- Machine-readable registry: `docs/req/requirements.yaml` (primary requirements),
  `docs/req/requirements-options.yaml` (option pool), `docs/req/req-schema.json`
  (CI schema).
- TODO: describe requirement volatility, how ambiguities were resolved, and the
  MoSCoW tradeoffs (evidence: registry history, review memos).

## 3. Architecture

- Master constraints: `architecture-blueprint.md`.
- Decisions: `docs/architecture/adr/` (e.g. `001-eval-harness.md`).
- Invariants: `docs/architecture/invariants.md`.
- Trace matrix: `docs/architecture/trace-matrix.md`.
- TODO: summarise the chosen architecture and the alternatives considered.

## 4. Verification and governance

- Six blocking gates: `.github/workflows/ci.yml`, `scripts/ci/`.
- Verification constraints: `docs/code-governance/verification-constraints.md`.
- Evidence: `docs/evidence/`.
- TODO: report defect trends, guard catches, and coverage.

## 5. Process quality evidence

- TODO: requirement volatility, defect trends, ambiguity resolution (point to
  `docs/debt-register.md`, `docs/bug-diary.md`, review memos).

## 6. How artifacts stayed co-evolving

- TODO: describe how requirements changed and how architecture, tests, and
  governance files were updated together.

## 7. What human oversight caught that the agent did not

- TODO: concrete examples from the session transcripts
  (`transcripts/<student-id>-<student-name>.md`).

## 8. Individual reflections (one short paragraph each, name + student ID)

> 300–500 words per member. TODO: each member writes their own; do not invent.

- **TODO (name, student ID):** TODO.

## Appendix A — Relation to the AI-use log

All code/prompt changes trace to AI-agent sessions; see `docs/ai-use-log.yaml`.
