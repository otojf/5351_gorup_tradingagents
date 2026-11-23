# Review Memos (D4)

Real review records for the pull requests that shaped the final integration.
Each entry records the reviewer, date, verdict, the areas checked, and how the
review was resolved. PRs with no submitted review are recorded as such and are
not given an invented verdict.

## PR #6 — NFR-E1: evaluation harness + six blocking CI gates

- **Reviewer:** k1160967796
- **Date:** 2026-11-19
- **Verdict:** CHANGES REQUIRED
- **Change summary:** added the offline evaluation harness, golden set, manifest,
  before/after comparison, and six blocking CI gates.
- **Areas reviewed:** spec/evidence alignment (trace-matrix and registry
  referenced two nonexistent tests); architecture (ADR-001 and the harness
  boundary were acceptable); code/test (37 eval/gate tests passed, but
  `prompt_snapshot` was a label rather than a hash and NFR-E1 metrics lacked
  assertions); security (no secrets found); efficiency (offline run; efficiency
  evidence incomplete); operational metadata (AI-use log/evidence required).
- **Resolution:** addressed in `b2694db` + `665e0a8`; delivered to `main` through
  integration PR #14 (`1cc1d9f`). The review report is attached to the PR review.

## PR #9 — FR-C2: skip unconfigured FRED once per analysis run

- **Reviewer:** k1160967796
- **Date:** 2026-11-19
- **Verdict:** CHANGES REQUIRED
- **Change summary:** skip an unconfigured FRED vendor once per run instead of
  retrying it repeatedly.
- **Areas reviewed:** spec/test quality (26 targeted tests passed; 0 HTTP,
  timeout, concurrency and isolation cases covered); architecture (no blocking
  issue); integration (the A1 gate would turn the path tests' `Overweight` into
  `REVIEW`); CI/operational (old workflow; AI-use-log format conflict). Code
  itself required essentially no change.
- **Resolution:** cross-PR test semantics and AI-use log aligned in the
  integration branch; delivered through PR #14 (`1cc1d9f`).

## PR #11 — FR-B2: conclusion citation checker + annotated D5 transcript

- **Reviewer:** k1160967796
- **Date:** 2026-11-19
- **Verdict:** CHANGES REQUIRED
- **Change summary:** offline conclusion-citation checker, evidence/provenance
  updates, and a D5 annotated transcript.
- **Areas reviewed:** spec alignment and evidence (citation outcomes and
  traceability); code/test quality (offline tests and CLI exit behavior);
  security (no secrets); operational metadata (AI-use log/D5 evidence).
- **Resolution:** author follow-ups `04ad26f` + `8638e57` were merged through
  PR #14 (`1cc1d9f`).

## PR #12 — FR-A1: deterministic risk gate

- **Reviewer:** k1160967796
- **Date:** 2026-11-19
- **Verdict:** CHANGES REQUIRED
- **Change summary:** deterministic risk gate and its integration into the
  portfolio-manager boundary.
- **Areas reviewed:** spec fit criteria (risk verdicts and audit trail);
  architecture (gate boundary/ADR); code and tests (invariant tests existed but
  four gaps remained); security/efficiency (offline, no secrets; audit
  persistence); operational metadata. The blocking gaps were: approved HOLD was
  downgraded to `REVIEW`, `position_sizing` was not read, production callers did
  not supply `risk_portfolio`, and malformed input could crash instead of
  failing closed.
- **Resolution:** fixed in `b2d240b` (approved HOLD semantics, sizing parsing,
  config/CLI `--risk-portfolio` injection, fail-closed malformed input; tests
  tightened), delivered through PR #14 (`1cc1d9f`).

## PR #13 — integration: D8 + A1 fixes + D5/prompts

- **Reviewer:** k1160967796
- **Date:** 2026-11-20
- **Verdict:** APPROVE
- **Change summary:** D8 physical `src/` + `test/offline|live` layout, A1 ported
  fixes, Appendix D, restored versioned prompts.
- **Areas checked:** CI 10/10 green (six gates + smoke), local 1789 passed,
  clean-checkout verification, AI-use-log evidence. No blocking comments.
- **Resolution:** merged to `integration/team-features` as `5801e5f`.

## PR #14 — integration delivery to main

- **Reviewer:** 1078622509
- **Date:** 2026-11-20
- **Verdict:** APPROVE
- **Change summary:** final integration of the five feature workstreams, D8
  structure, A1 fixes, Appendix D, and prompts.
- **Areas checked:** main's 9 required checks + smoke all green; one non-author
  approval; known gaps documented (D5/D6/docs, deferred eval adaptation).
- **Resolution:** merged to `main` as `1cc1d9f` (2026-11-22).

## PR #10 — FR-D2: structured-output retry / DEGRADED

- **Reviewer:** none submitted
- **Verdict:** not reviewed
- **Change summary:** retry structured output twice, mark RETRY/DEGRADED and
  continue instead of silently degrading.
- **Note:** merged through the integration path without a submitted review.
  No verdict is invented here; this gap is recorded honestly.

## PR #16 — docs: D4 review memo, README purpose/architecture, D1 statuses

- **Reviewer:** degna9838-pixel
- **Date:** 2026-11-23
- **Verdict:** APPROVE
- **Change summary:** filled the D4 review memo with the real review records for
  PRs #6/#9/#10/#11/#12/#13/#14, added the README purpose/architecture sections
  and GitHub URL, and updated the D1 requirement statuses.
- **Areas checked:** reviewer/verdict entries matched the submitted GitHub
  reviews and the referenced integration merges; no invented verdicts; document
  consistency; no secrets.
- **Resolution:** merged to `main` as `b63c168` (2026-11-23).

## PR #17 — docs(d5): Jin Li FR-D2 reimplementation transcript

- **Reviewer:** otojf
- **Date:** 2026-11-23
- **Verdict:** APPROVE
- **Change summary:** added the annotated D5 transcript for Jin Li (60263031)
  covering the FR-D2 reimplementation session.
- **Areas checked:** D5 format (session header, session ID, 177 messages, 6-item
  human intervention index with rationale); content alignment with the FR-D2
  retry/degradation design; security (no secrets); operational metadata (the
  AI-use log now points at the transcript, PR #18).
- **Resolution:** merged to `main` as `6e7d12a` (2026-11-23).

## PR #15 — docs(d5): ZHANG Yating FR-A1 transcript

- **Reviewer:** otojf
- **Date:** 2026-11-23
- **Verdict:** APPROVE
- **Change summary:** added the annotated D5 transcript for ZHANG Yating
  (60868911), covering the main FR-A1 decision-safety session and the earlier
  feasibility session.
- **Areas checked:** D5 format (session metadata, intervention index, 19
  annotated interventions with rationale); content alignment with the FR-A1
  scope and the supervised classification -> test-plan -> implementation ->
  audit/demo sequence; security (no secrets; the `sk-` hits are substrings of
  `risk-controlled` / `risk-gate`); all 10 required checks green after
  retargeting the base to `main`.
- **Resolution:** merged to `main` as `0f233da` (2026-11-23).
