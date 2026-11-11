# test/live/ — Mapping Only (No Physical Migration)

The course's §5/D8 structure names `test/live/` for API-dependent tests. This
repository keeps such tests inside `tests/`, selected by the `integration`
marker, and does **not** physically move them. This file maps the spec path to
the real location.

| Spec path | Actual path | Selection |
|---|---|---|
| `test/live/` | tests marked `@pytest.mark.integration` within `tests/` | Run only when asked: `pytest -m integration`. Excluded by default (`addopts = -m "not integration"`). |

Live tests require real API access (provider keys, vendor data) and are never run
in CI or the default offline suite.

To run the full suite including live tests: `pytest -m ""` (requires configured
API access). The default `pytest -q` runs only offline tests.

Full mapping: `docs/architecture/repository-structure-mapping.md`.
