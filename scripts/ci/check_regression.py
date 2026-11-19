#!/usr/bin/env python3
"""Gate 5: regression.

Course D7 gate 5: every change runs the full prior test suites; any regression
blocks the merge. This script runs the whole default pytest suite (offline,
``not integration`` per pyproject addopts).

Note: this gate intentionally does NOT include ``tests/test_ci_gates.py``'s
"run the full suite" test, which would recurse. The CI-gates tests skip the
regression-recursion path; see ``tests/test_ci_gates.py``.

Usage::

    python scripts/ci/check_regression.py

Exit 0 = full suite passes; exit 1 = a test fails.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        print("FAIL: gate 5 (regression)")
        print(output[-4000:])
        return 1
    print("PASS: gate 5 (regression)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
