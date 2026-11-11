"""FR-A1 Deterministic Risk Gate — offline acceptance tests.

These tests are authored before production implementation (see
``docs/req/fr-a1-test-plan.md`` and ``docs/architecture/adr/adr-fr-a1-risk-gate.md``).
They exercise the agreed contract at ``tradingagents.risk_gate``. The package does
not exist yet, so importing a test module fails with ``ModuleNotFoundError``;
that is the expected pre-implementation state and is reported honestly, never
counted as a pass.
"""
