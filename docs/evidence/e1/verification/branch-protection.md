# Branch Protection — Required Checks

Branch protection for `main` must require passing CI, and changes to
safety-critical paths must require human review (course D7). This document lists
the **exact** required-check names and a command to configure them.

Status: **not yet configured.** Configuration must be done by a repository admin
(or from the Windows side where `gh` is authenticated with admin rights). It is
not done by these scripts and is not pushed by the agent.

## Required check names

GitHub matches required checks by the **job `name:`** shown in the Actions UI,
after matrix expansion. The six gate jobs produce:

| Job ID | Required check name(s) |
|---|---|
| `gate-1-test-approval` | `gate-1-test-approval` |
| `gate-2-static-analysis` | `gate-2-static-analysis` |
| `gate-3-schema` | `gate-3-schema` |
| `gate-4-semantic-eval` | `gate-4-semantic-eval` |
| `gate-5-regression` | `gate-5-regression (py3.11)`, `gate-5-regression (py3.12, America/New_York)`, `gate-5-regression (py3.13)`, `gate-5-regression (py3.14)` |
| `gate-6-ai-use-log` | `gate-6-ai-use-log` |

**Note (correction):** the `gate-5-regression` matrix has **4** entries, not 5.
Its `strategy.matrix.include` entry `{python-version: "3.12", tz: America/New_York}`
**merges** the `tz` value into the existing `3.12` combination; it does not add a
fifth combination. So gate-5 yields 4 check names. Total required checks = **9**
(5 single jobs + 4 matrix-expanded gate-5 checks).

`gate-1-test-approval` and `gate-6-ai-use-log` only run on `pull_request`, which
is exactly when branch protection evaluates required checks, so they are valid
required checks.

## Configure with `gh` (repository admin)

Run from the repo root on a machine where `gh auth status` shows admin on the
repo. Merging safety-critical changes must additionally require human review
(approving review), which is set below.

```bash
gh api -X PUT \
  repos/otojf/5351_gorup_tradingagents/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=gate-1-test-approval" \
  -f "required_status_checks[contexts][]=gate-2-static-analysis" \
  -f "required_status_checks[contexts][]=gate-3-schema" \
  -f "required_status_checks[contexts][]=gate-4-semantic-eval" \
  -f "required_status_checks[contexts][]=gate-5-regression (py3.11)" \
  -f "required_status_checks[contexts][]=gate-5-regression (py3.12, America/New_York)" \
  -f "required_status_checks[contexts][]=gate-5-regression (py3.13)" \
  -f "required_status_checks[contexts][]=gate-5-regression (py3.14)" \
  -f "required_status_checks[contexts][]=gate-6-ai-use-log" \
  -F "enforce_admins=true" \
  -f "required_pull_request_reviews[required_approving_review_count]=1" \
  -F "restrictions="
```

If the exact matrix display names drift, verify them after the first CI run with:

```bash
gh api repos/otojf/5351_gorup_tradingagents/commits/<sha>/check-runs --jq '.check_runs[].name'
```

## Who executes this

- Requires **Windows side or a repo admin** with an authenticated `gh`.
- The agent does not configure branch protection and does not push.
- The `verify` step: open a knowingly-bad PR (e.g., a commit that fails the
  schema gate) and confirm GitHub blocks the merge with "Required statuses must
  pass".
