# NFR-E1 Verification Evidence

`test-results.txt` holds the **actual** captured output of the verification
commands run locally on 2026-11-11. It contains the real command lines,
stdout/stderr, and exit codes — not a summary. These are **local** captures; the
GitHub CI has not run yet, so no CI results are claimed.

Gate 1 (test-approval) now passes locally: the human approval record was filled
by HUANG SIYING (60572233) on 2026-11-11. The earlier local capture of the gate failing
on a TODO record remains in the transcript, not in the current evidence file.

## Commands and how to reproduce

Run from the repository root:

```bash
# registry schema validation
python -c "import json,yaml,jsonschema; \
  json.load(open('docs/req/req-schema.json')); \
  jsonschema.Draft202012Validator(json.load(open('docs/req/req-schema.json'))) \
    .validate(yaml.safe_load(open('docs/req/requirements.yaml'))); print('schema OK')"

# eval harness tests (offline, deterministic)
python -m pytest tests/test_eval_harness.py -q

# lint
python -m ruff check eval tests/test_eval_harness.py
```

## Status

Captured (local, 2026-11-11). CI pending; branch protection documented in
`branch-protection.md` (not yet configured).

## What these results establish

- The registry validates against its JSON schema.
- The eval harness is deterministic and repeatable under the scripted source.
- The six gate scripts fire on deliberately bad local inputs
  (`tests/test_ci_gates.py`); real GitHub bad-PR evidence is still pending.
