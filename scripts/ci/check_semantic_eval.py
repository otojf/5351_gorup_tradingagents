#!/usr/bin/env python3
"""Gate 4: semantic evaluation.

Course D7 gate 4: for a prompt or model change, replay a fixed evaluation set
against quality thresholds before the change can reach production. This script
replays the NFR-E1 evaluation set by running the eval harness tests offline.

Honest limit: the eval set is deterministic under a scripted source (it proves
harness/graph structure determinism), not real-input semantic quality. The
"threshold" here is that the fixed golden set still produces its expected
ratings and stable output.

Usage::

    python scripts/ci/check_semantic_eval.py

Exit 0 = eval harness passes; exit 1 = it fails.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", "tests/test_eval_harness.py", "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        print("FAIL: gate 4 (semantic eval)")
        print(output)
        return 1
    print("PASS: gate 4 (semantic eval; fixed golden set, scripted source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
