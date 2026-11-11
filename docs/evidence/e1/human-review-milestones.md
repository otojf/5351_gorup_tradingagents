# NFR-E1 Human Review & Approval Milestones

Recorded from the project's human-review dialogue. Only milestones that actually
happened are listed; no timestamps, decisions, or approvals are invented.

## 1. Scope decision

- Human constrained scope: keep NFR-E1 as the single primary entry; do **not**
  lift FR-E1/FR-E2/FR-E3/INV-E1 to top level (pending team/instructor
  confirmation). No `src/`/`test/` physical migration — document a mapping.
- Human set the six-gate minimum honest version and required any uncovered
  sub-checks (type-check, contract, security, permission) to be stated, not
  faked.

## 2. Phase 1 — registry + schema

- Human approved adding `jsonschema>=4` to `dev` extras, updating `updated` to
  `2026-11-11`, and nested supporting entries.
- Human required demonstrating a bad field / bad status is rejected. Done:
  both bad registries fail validation (see session transcript).

## 3. Phase 1 review follow-ups

- Human required widening the ID pattern to accept `NFR-GOV-01` / `NFR-SEC-01`
  before governance entries are added, with a validation case. Done.
- Human required FR-E1 stay `partial` until the Phase 3 3-case compare passes.
  Done.

## Pending (not yet approved)

- Phase 3 test fixes and Phase 4 six gates + branch protection are planned, not
  yet executed.
