"""Fixtures shared by the FR-A1 risk-gate tests.

The suite is offline by construction: the repository's top-level ``conftest.py``
already refuses socket connects for every non-integration test, and the pure
engine must not depend on network, file I/O, or an LLM.

There is deliberately no module-level ``importorskip`` and no production stub:
each test imports ``tradingagents.risk_gate`` via ``_support.require_engine()`` so
that, before implementation, tests are collected and fail for real. That RED state
is the evidence the tests actually exercise the gate.
"""
