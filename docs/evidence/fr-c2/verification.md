# FR-C2 verification - 2026-11-12

## Environment

Windows, Python 3.14.6. Exact key versions are recorded in
test-environment.json and local compatibility pins in test-constraints.txt.
`pip check`: No broken requirements found.

The initial newest-wheel environment could not load several binary extensions
under Windows application control. Installing compatible released versions
that still satisfy the project's requirements resolved this. No security
policy was changed; no production requirements were relaxed.

## Results

- Targeted initial run: 74 passed, 8 subtests passed (before the final additional
  core-error-subtype regression test).
- Final default offline suite: **1422 passed, 6 skipped, 1 deselected, 24 warnings,
  100 subtests passed in 38.33s**. Raw output: full-test-results.txt.
- Ruff 0.17.4, full repository: All checks passed.
- git diff --check: passed.
- New checks include same-run concurrent requests, separate concurrent runs,
  next-run recovery, whitespace-only credentials, fallback, exception cleanup,
  normal/debug/direct-stream graph completion, and preservation of a core
  supplier's original configuration-error subtype.

The six skips concern POSIX-specific checks on Windows and optional Bedrock
dependencies. One integration test is deselected by the repository default.
The warnings concern model-name fixtures, not failed assertions.

## Controlled before/after demonstration

See before-after.json. The original router and modified function bodies were
executed with a synthetic absent key and blocked HTTP. Seven macro requests:

| Metric | Before | After |
|---|---:|---:|
| Simulated tool requests | 7 | 7 |
| FRED supplier function entries | 7 | 0 |
| HTTP requests | 0 | 0 |
| Related warning events | 14 | 1 |
| Structured vendor_skipped events | 0 | 1 |

This is a deterministic routing demonstration. It does not claim seven live
network retries were saved or that a real LLM made fewer tool calls. Full graph
completion is independently tested with scripted models and mocked vendors.

All runtime tests used synthetic credentials, dotenv loading was disabled, and
unit-test network guards remained enabled. No real API keys or paid LLM calls
were used. Live-market behavior and other operating systems were not tested.
