# Test Approval Record (Gate 1)

A code change must not merge unless the tests for the change were approved
**before** implementation began (course D7, blocking gate 1). This is a human
gate; `scripts/ci/check_test_approval.py` checks that this record is complete.

<!--
Fill every field below, then remove the "TODO" placeholders. The gate fails
until this is done (that is expected, not a bug).
-->

- approved_by: HUANG SIYING (60572233)
- approved_date: 2026-11-11
- test_scope: NFR-E1 eval harness tests (tests/test_eval_harness.py) and CI gate scripts (tests/test_ci_gates.py); test-first evidence in transcripts/opencode-nfr-e1-annotated.md.

## What was approved

- Requirement(s): NFR-E1 (with FR-E1, FR-E2, FR-E3, INV-E1)
- Tests approved before implementation: `tests/test_eval_harness.py`
  (golden set, manifest, run_suite isolation, before/after compare) and
  `tests/test_ci_gates.py` (six gate scripts).
- Evidence of test-first: the eval tests were written and run before the
  harness/tool-arg changes they cover.

## Notes

This record covers the NFR-E1 evaluation harness. Each further change that
touches code or prompts requires its own approval entry (or a linked memo).
