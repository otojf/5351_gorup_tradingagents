#!/usr/bin/env python3
"""Gate 6: AI-use log.

A pull request that changes code or prompts must also update the AI-use log
(``docs/ai-use-log.yaml``), per course D7, gate 6. This script checks:

- the AI-use log exists and parses, and
- when the change touches code/prompt paths, the log has at least one entry
  whose ``files_changed`` overlaps those paths (or, if a changed path is not
  enumerated, that the log's newest entry is dated/covered for this change).

Honest limit: this cannot verify that a log entry is *true*, only that a
matching entry exists. It is a presence/coverage check.

Usage::

    python scripts/ci/check_ai_use_log.py --changed-file a.py --changed-file b.md
    python scripts/ci/check_ai_use_log.py --changed-file-list files.txt

The changed-file list is the CI-provided diff. When no files are given (local
run), the gate treats it as "check the log is present and well-formed".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

DEFAULT_LOG = Path("docs/ai-use-log.yaml")

# A change is "code or prompt" if it touches one of these prefixes.
_CODE_PROMPT_PREFIXES = (
    "tradingagents/",
    "cli/",
    "eval/",
    "tests/",
    "scripts/",
    "prompts/",
)
_CODE_PROMPT_FILES = ("main.py", "AGENTS.md", "Prompt.md")


def _is_code_or_prompt(path: str) -> bool:
    normalized = path.strip().lstrip("./")
    return (
        normalized.startswith(_CODE_PROMPT_PREFIXES)
        or normalized in _CODE_PROMPT_FILES
    )


def check(changed_files: list[str], log_path: Path = DEFAULT_LOG) -> list[str]:
    """Return a list of problems; empty means the log covers the change."""
    if not log_path.exists():
        return [f"missing AI-use log: {log_path}"]
    try:
        log = yaml.safe_load(log_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"AI-use log is not valid YAML: {exc}"]

    entries = (log or {}).get("entries") or []
    if not entries:
        return ["AI-use log has no entries"]

    relevant = [f for f in changed_files if _is_code_or_prompt(f)]
    if not relevant:
        return []  # docs-only change: log presence is enough

    covered: set[str] = set()
    for entry in entries:
        for changed in entry.get("files_changed") or []:
            covered.add(str(changed).strip().lstrip("./"))

    missing = [
        f for f in relevant
        if not _covered_by(f, covered)
    ]
    if missing:
        return [
            "code/prompt change not covered by any AI-use log entry: "
            + ", ".join(missing)
        ]
    return []


def _covered_by(changed: str, covered: set[str]) -> bool:
    """A changed path is covered if a log entry lists it or a parent dir."""
    changed = changed.strip().lstrip("./")
    return any(changed == c or changed.startswith(c.rstrip("/") + "/") for c in covered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate 6: AI-use log")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--changed-file-list", type=Path)
    args = parser.parse_args(argv)

    files = list(args.changed_file)
    if args.changed_file_list:
        files += [
            line.strip()
            for line in args.changed_file_list.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    problems = check(files)
    if problems:
        print("FAIL: gate 6 (AI-use log)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASS: gate 6 (AI-use log)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
