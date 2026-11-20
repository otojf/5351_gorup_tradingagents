#!/usr/bin/env python3
"""Gate 1: test-approval.

A code change must not merge unless the tests for the change were approved
before implementation began (course D7, gate 1). This is a **human** gate: this
script only checks that a completed approval record exists.

The record is ``docs/evidence/e1/test-approval.md`` and must contain, per D7:

- the approving human(s) (``approved_by``), and
- the date (``approved_date``), and
- the test scope (``test_scope``).

Until the team fills it in, ``approved_by`` stays ``TODO`` and this gate fails
(exit 1). That is the expected, honest state, not a bug.

Usage::

    python scripts/ci/check_test_approval.py [--record PATH]

Exit 0 = approved record present and complete; exit 1 = missing/incomplete.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_RECORD = Path("docs/evidence/e1/test-approval.md")

_REQUIRED_FIELDS = ("approved_by", "approved_date", "test_scope")
# A field is "filled" when its value is non-empty and not a TODO placeholder.
_TODO = re.compile(r"\b(todo|tbd|tba|pending)\b", re.IGNORECASE)


def check_record(path: Path) -> list[str]:
    """Return a list of problems; empty means approved."""
    if not path.exists():
        return [f"missing approval record: {path}"]

    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    fields = _parse_fields(text)
    for name in _REQUIRED_FIELDS:
        value = fields.get(name, "").strip()
        if not value:
            problems.append(f"field '{name}' is missing or empty")
        elif _TODO.search(value):
            problems.append(f"field '{name}' is still a placeholder: {value!r}")
    return problems


def _parse_fields(text: str) -> dict[str, str]:
    """Parse ``- approved_by: ...`` / ``| approved_by | ... |`` style lines."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        # "- approved_by: Alice" or "approved_by: Alice"
        m = re.match(r"^(?:[-*]\s*)?([A-Za-z_]+)\s*:\s*(.*)$", stripped)
        if m and m.group(1) in _REQUIRED_FIELDS:
            fields[m.group(1)] = m.group(2).strip()
        # "| approved_by | Alice |"
        elif stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] in _REQUIRED_FIELDS:
                fields[cells[0]] = cells[1]
    return fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate 1: test-approval")
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    args = parser.parse_args(argv)

    problems = check_record(args.record)
    if problems:
        print("FAIL: gate 1 (test-approval)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASS: gate 1 (test-approval)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
