# test/offline/ — Mapping Only (No Physical Migration)

The course's §5/D8 structure names `test/offline/` for deterministic tests. This
repository keeps its tests in `tests/` and does **not** physically move them.
This file maps the spec path to the real location.

| Spec path | Actual path | Contents |
|---|---|---|
| `test/offline/` | `tests/` | All deterministic, offline tests. By default `pytest` runs with `-m "not integration"` (see `pyproject.toml`), so live tests are excluded. |
| `test/offline/` (eval) | `tests/test_eval_harness.py` | NFR-E1 eval harness tests (golden set, manifest, isolation, compare). |
| `test/offline/` (gates) | `tests/test_ci_gates.py` | Six CI gate scripts and their bad-input self-tests. |

Offline means: vendors and LLMs are monkeypatched/stubbed; no network; no API
keys. Deterministic repeats are proven by `run_suite`.

Full mapping: `docs/architecture/repository-structure-mapping.md`.
