# FR-B2 integration handoff after PR #11 review

Updated on 2026-11-20. The feature is accepted against FR-B2 in
`docs/req/requirements-options.yaml`. The current consolidated registry labels
the broader evidence feature as FR-B1. The team should reconcile the registry
and trace matrix with the requirements actually delivered by each owner.

## Requirement trace

| FR-B2 condition | Implementation | Verification |
|---|---|---|
| Mark missing or unresolvable citations UNTRACEABLE | `fr_b2/check_citations.py::check_claim` | `fr_b2/tests/test_check_citations.py::test_five_negatives_each_have_expected_reason` |
| Exclude these findings from supported | `fr_b2/check_citations.py::run_check` | `fr_b2/tests/test_check_citations.py::test_summary_counts` |
| Keep positive evidence readable in a mixed batch | `fr_b2/check_citations.py::check_claim` | `fr_b2/tests/test_check_citations.py::test_missing_evidence_file_is_separate_from_positive` |
| Verify saved evidence against registered digests | `fr_b2/verify_evidence.py::verify_manifest` | `fr_b2/tests/test_review_followups.py::test_registered_evidence_hashes_match` |

The result describes the supplied claims list. A resolvable reference is the
meaning of SUPPORTED in this checker. Evaluating whether a cited passage
supports the reasoning or a derived calculation requires its own method.
The snapshot is an independent fetch made before the original analysis.
Digests were registered after capture, on 2026-11-20.

## CI and central AI-use log

This branch adds `fr_b2/tests` to the default pytest collection paths. Its
existing test job now runs both the original tests and the FR-B2 tests, including
evidence integrity. The E branch's default pytest regression job will also
collect them when this configuration is retained during integration.

Owner E still needs to confirm the following in the six-gate branch:

1. Include `fr_b2/` in the code/prompt prefixes checked by
   `scripts/ci/check_ai_use_log.py` and add a negative test for an unlogged change
   to `fr_b2/check_citations.py`.
2. Append the entries in this directory's `ai-use-log.yaml` to the central
   `docs/ai-use-log.yaml`, preserving E's existing entries. The original build
   used OpenCode; the current review follow-up used Codex with the author's
   approval.
3. Use the local regression tests when checking the combined regression gate.
   The current PR's Actions jobs and the later six-gate workflow are distinct.

## Eval manifest fields

Owner E can read the JSON produced by `python -m fr_b2.check_citations` and map
its existing summary fields as follows, subject to the team's manifest schema:

| Checker field | Example | Meaning |
|---|---:|---|
| `summary.total` | 6 | Supplied claim records checked |
| `summary.supported` | 1 | Records with a resolvable citation |
| `summary.untraceable` | 5 | Records with missing or invalid references |
| `results[].reason` | `missing_citation` | Per-record failure reason |

For the sample, `1/6` is the citation-resolution fraction among the six supplied
records. The fixtures repeat one real statement with different citations, so
that fraction is an acceptance-test result. It does not measure all claims in
the AAPL report. The eval manifest should label the input scope as
`supplied_claims` and retain the result-file path.

FR-B2 exports the fields above; wiring them into E's run manifest remains a
team integration task. This branch supplies the handoff without assigning
values to an evaluation run that has not called the checker.
