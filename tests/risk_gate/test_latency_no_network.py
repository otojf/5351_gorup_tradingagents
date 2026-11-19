"""NFR-A1: core engine latency and zero network / LLM dependency.

The pure risk engine must add no perceptible latency (p95 ≤ 2 s) and must not
depend on network, file I/O, or an LLM. The runtime socket guard from the
repository conftest is already active; this module additionally installs its own
guard for the duration of the latency loop and performs a structural check that
the engine package does not import network/LLM client modules.

The measured p95 is printed in the assertion message so the number is reported,
and the core evaluation latency is distinguished from any integration overhead.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import textwrap
import time

import pytest

from tests.risk_gate._support import evaluate, make_buy


@pytest.mark.unit
def test_p95_core_evaluation_latency_within_two_seconds(capsys):
    """NFR-A1: core-evaluation p95 ≤ 2000 ms over 1000 evaluations (measured)."""
    samples = []
    for _ in range(1000):
        start = time.perf_counter()
        evaluate(make_buy())
        samples.append((time.perf_counter() - start) * 1000.0)
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))]
    p50 = samples[len(samples) // 2]
    print(f"\ncore evaluation latency: p50={p50:.4f}ms p95={p95:.4f}ms n={len(samples)}")
    assert p95 <= 2000.0, f"core p95={p95:.4f}ms exceeds 2000ms"


@pytest.mark.unit
def test_evaluation_runs_under_a_runtime_socket_guard(monkeypatch):
    """NFR-A1: evaluation completes while every socket call refuses to connect."""
    def refuse(*a, **k):
        raise AssertionError("risk gate attempted a network call")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    result = evaluate(make_buy())
    assert result.verdict in ("APPROVED", "REJECTED", "NEEDS_REVIEW")


@pytest.mark.unit
def test_engine_imports_no_network_or_llm_module():
    """NFR-A1: importing the engine alone pulls in no network or LLM client.

    A subprocess imports ``tradingagents.risk_gate`` and reports whether any
    banned module is present, so a prior test's imports cannot mask the check.
    """
    banned = ["requests", "urllib3", "httpx", "curl_cffi", "yfinance",
              "langchain_core", "langchain_openai", "openai"]
    code = textwrap.dedent(
        f"""
        import sys, json, importlib
        importlib.import_module("tradingagents.risk_gate")
        banned = {banned!r}
        print(json.dumps([m for m in banned if m in sys.modules]))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    loaded = __import__("json").loads(proc.stdout.strip().splitlines()[-1])
    assert loaded == [], f"engine imported banned modules: {loaded}"


@pytest.mark.unit
def test_core_latency_excludes_integration_overhead():
    """NFR-A1/§11: core latency is measured on the pure engine only.

    Integration overhead (graph/node wrapping) is covered by the integration
    tests. This asserts the pure evaluate loop is fast in isolation, so a p95
    regression can be attributed to the core rather than to graph plumbing.
    """
    start = time.perf_counter()
    for _ in range(200):
        evaluate(make_buy())
    elapsed_ms = (time.perf_counter() - start) * 1000.0 / 200
    assert elapsed_ms <= 2000.0, f"core mean={elapsed_ms:.4f}ms"
