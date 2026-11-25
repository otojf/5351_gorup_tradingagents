# Risk List (D2.10, optional)

Assumptions that could become defects, with review triggers. Risks from the
integrated features replace the earlier "other branches" placeholder.

| ID | Risk | Assumption it rests on | If it materializes | Review trigger |
|---|---|---|---|---|
| RISK-01 | Scripted source drifts from production patch points | The harness patches the same vendor/router/LLM points production uses | Harness passes while production breaks | A vendor/router refactor; harness test failures |
| RISK-02 | Eval claim overstated | "Deterministic" applies only under the scripted source | Reviewers mistake it for real-input reproducibility | Any report/demo wording about the eval |
| RISK-03 | Gates are bypassable | Branch protection + required checks are configured correctly | Bad merge slips through | Changing `.github/workflows/ci.yml` or branch protection |
| RISK-04 | Test-approval is superficial | Human fills the record honestly before coding | Gate 1 satisfied without real approval | Any PR review inconsistency |
| RISK-05 | Manifest nulls hide gaps | A/B/D will fill degradations/risk/traceability | Manifest overstates completeness | A/B/D producer changed or a manifest schema change |
| RISK-06 | Compliance docs go stale | Docs are co-evolved with code | Docs contradict code | Code change touching a documented contract |
| RISK-07 | Matrix check-name mismatch | Required-check names match the Actions UI | Branch protection blocks green PRs | After a workflow change; verify with `gh api .../check-runs` |
| RISK-08 | Single-context multi-case misuse | `run_suite` rejects it | (mitigated) wrong-instrument runs | A new caller of `run_suite` |
| RISK-09 | Risk gate scope is narrower than the prose | The delivered gate covers cash-funded long BUY; SELL/short and the approval queue are deferred | A SELL/short path publishes without the same hard checks | A SELL/short feature is implemented; FR-A2 is approved |
| RISK-10 | Citation checker is read as a truth judgment | It verifies resolution, not logical support or arithmetic | A reader over-trusts a resolved but wrong claim | Report or README wording changes around FR-B2 |
| RISK-11 | FRED skip state leaks across runs | Run-scoped state is attached to a copy of the config | A later run keeps skipping after credentials are restored | A new caller reuses a config object; FR-C2 tests change |
| RISK-12 | Token budget is absent | NFR-C1 is partial; only FR-C2 is delivered | Cost overruns are not blocked at runtime | NFR-C1 work starts or a provider/model changes |
| RISK-13 | Gate 2 type-check is scoped | Only safety-critical modules are checked with mypy | A type regression in the upstream baseline is not caught | A baseline module becomes safety-relevant; DEBT-02 is retired |
