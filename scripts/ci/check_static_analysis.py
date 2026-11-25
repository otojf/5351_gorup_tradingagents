#!/usr/bin/env python3
"""Gate 2: static analysis.

Course D7 gate 2 asks for lint, type-checking and dependency checks on every
commit, plus contract/security/API-surface/permission checks on PRs touching
safety paths. This gate runs:

- ``ruff check``             (lint)
- ``pip check``              (installed-dependency consistency)
- ``compileall``             (syntax / import compile)
- ``mypy`` on the new safety-critical packages and integration seams
- ``scripts/ci/check_permissions.py`` (permission-model consistency)
- ``scripts/ci/check_secrets.py``     (targeted secret scan)
- layering + prompt-integrity tests   (contract checks)
- import smoke of the public packages (API surface)

Limits, stated rather than hidden: mypy covers the safety-critical modules, not
the whole upstream baseline; contract/API checks are the existing layering /
prompt-integrity tests plus an import smoke, not a full API-compatibility
suite. The remaining full-repo type-check is tracked as DEBT-02.

Usage::

    python scripts/ci/check_static_analysis.py

Exit 0 = all covered checks pass; exit 1 = any fails.
"""

from __future__ import annotations

import compileall
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PY_DIRS = ("src/tradingagents", "src/cli", "src/eval", "src/fr_b2", "scripts")
_TYPE_TARGETS = (
    "src/tradingagents/risk_gate",
    "src/fr_b2",
    "src/eval",
    "src/tradingagents/agents/structured.py",
    "src/tradingagents/dataflows/vendor_skip.py",
    "src/tradingagents/dataflows/router.py",
    "src/tradingagents/agents/managers/portfolio_manager.py",
    "src/tradingagents/agents/state.py",
)


def _run(cmd: list[str], *, extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        cmd, capture_output=True, text=True, cwd=ROOT, env=env
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def check() -> tuple[list[str], list[str]]:
    """Return (failures, passes)."""
    failures: list[str] = []
    passes: list[str] = []
    src_env = {"PYTHONPATH": str(ROOT / "src")}

    code, out = _run([sys.executable, "-m", "ruff", "check", "."])
    (failures if code else passes).append(f"ruff check: {out or 'clean'}")

    code, out = _run([sys.executable, "-m", "pip", "check"])
    (failures if code else passes).append(f"pip check: {out or 'clean'}")

    dirs = [d for d in _PY_DIRS if (ROOT / d).is_dir()]
    ok = True
    compile_out = []
    for d in dirs:
        compiled = compileall.compile_dir(str(ROOT / d), quiet=1)
        ok = ok and bool(compiled)
        compile_out.append(f"{d}={'ok' if compiled else 'FAIL'}")
    (passes if ok else failures).append("compileall: " + ", ".join(compile_out))

    type_targets = [str(ROOT / p) for p in _TYPE_TARGETS if (ROOT / p).exists()]
    code, out = _run(
        [
            sys.executable, "-m", "mypy",
            "--ignore-missing-imports", "--follow-imports=skip",
            "--no-error-summary", *type_targets,
        ]
    )
    (failures if code else passes).append(f"mypy safety-critical: {out or 'clean'}")

    for script in ("check_permissions.py", "check_secrets.py"):
        code, out = _run([sys.executable, str(ROOT / "scripts/ci" / script)])
        (failures if code else passes).append(f"{script}: {out}")

    code, out = _run(
        [
            sys.executable, "-m", "pytest", "-q",
            "test/offline/test_layering.py", "test/offline/test_prompt_integrity.py",
        ],
        extra_env=src_env,
    )
    (failures if code else passes).append(f"contract tests: {out or 'clean'}")

    code, out = _run(
        [sys.executable, "-c", "import tradingagents, cli.main, eval, fr_b2"],
        extra_env=src_env,
    )
    (failures if code else passes).append(f"API-surface import: {out or 'ok'}")

    return failures, passes


def main() -> int:
    failures, passes = check()
    for p in passes:
        print("OK   " + p)
    if failures:
        print("FAIL: gate 2 (static analysis)")
        for f in failures:
            print(f"  - {f}")
        print(
            "  NOT covered: full-repo type-check (safety-critical modules only), "
            "and a full API-compatibility suite."
        )
        return 1
    print("PASS: gate 2 (static analysis)")
    print(
        "  NOT covered: full-repo type-check (safety-critical modules only), "
        "and a full API-compatibility suite."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
