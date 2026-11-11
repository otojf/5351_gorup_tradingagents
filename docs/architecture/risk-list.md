# Risk List (D2.10, optional)

Assumptions that could become defects, with review triggers.

| ID | Risk | Assumption it rests on | If it materializes | Review trigger |
|---|---|---|---|---|
| RISK-01 | Scripted source drifts from production patch points | The harness patches the same vendor/router/LLM points production uses | Harness passes while production breaks | A vendor/router refactor; harness test failures |
| RISK-02 | Eval claim overstated | "Deterministic" applies only under the scripted source | Reviewers mistake it for real-input reproducibility | Any report/demo wording about the eval |
| RISK-03 | Gates are bypassable | Branch protection + required checks are configured correctly | Bad merge slips through | Changing `.github/workflows/ci.yml` or branch protection |
| RISK-04 | Test-approval is superficial | Human fills the record honestly before coding | Gate1 satisfied without real approval | Any PR review inconsistency |
| RISK-05 | Manifest nulls hide gaps | Owners A/B/D will fill degradations/risk/traceability | Manifest overstates completeness | A/B/D merge or a manifest schema change |
| RISK-06 | Compliance docs go stale | Docs are co-evolved with code | Docs contradict code | Code change touching a documented contract |
| RISK-07 | Matrix check-name mismatch | Required-check names match the Actions UI | Branch protection blocks green PRs | After the first CI run; verify with `gh api .../check-runs` |
| RISK-08 | Single-context multi-case misuse | `run_suite` rejects it | (mitigated) wrong-instrument runs | A new caller of `run_suite` |

> TODO (team): add risks from other feature branches; link each to a review
> trigger.
