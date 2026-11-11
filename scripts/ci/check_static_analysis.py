#!/usr/bin/env python3
"""Gate 2: static analysis (minimum honest version).

Course D7 gate 2 asks for lint, type-checking and dependency checks on every
commit, plus contract/security/API-surface/permission checks on PRs touching
safety paths. This script implements only the parts this repo can honestly run
today:

- ``ruff check``            (lint)
- ``pip check``             (installed-dependency consistency)
- ``python -m compileall``  (syntax / import compile)

NOT covered here (stated, not faked):

- type-checking (no mypy/pyright configured)
- contract / API-surface checks
- dedicated security scan (secret scan is INV-E1's separate concern)
- permission checks (no .opencode permission model yet)

Usage::

    python scripts/ci/check_static_analysis.py

Exit 0 = all covered checks pass; exit 1 = any fails.
"""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path

_PY_DIRS = ("tradingagents", "cli", "eval", "scripts")


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def check() -> tuple[list[str], list[str]]:
    """Return (failures, passes)."""
    failures: list[str] = []
    passes: list[str] = []

    code, out = _run([sys.executable, "-m", "ruff", "check", "."])
    (failures if code else passes).append(f"ruff check: {out or 'clean'}")

    code, out = _run([sys.executable, "-m", "pip", "check"])
    (failures if code else passes).append(f"pip check: {out or 'clean'}")

    dirs = [d for d in _PY_DIRS if Path(d).is_dir()]
    ok = True
    compile_out = []
    for d in dirs:
        compiled = compileall.compile_dir(d, quiet=1)
        ok = ok and bool(compiled)
        compile_out.append(f"{d}={'ok' if compiled else 'FAIL'}")
    (passes if ok else failures).append("compileall: " + ", ".join(compile_out))

    return failures, passes


def main() -> int:
    failures, passes = check()
    for p in passes:
        print(f"OK   {p}")
    if failures:
        print("FAIL: gate 2 (static analysis)")
        for f in failures:
            print(f"  - {f}")
        print("  NOT COVERED: type-check, contract, security, permission.")
        return 1
    print("PASS: gate 2 (static analysis; type-check/contract/security/permission NOT covered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
