#!/usr/bin/env python3
"""Gate 2 companion: permission-model check.

Course D7 gate 2 requires permission checks on pull requests touching
safety-relevant paths. This script validates the machine-readable model in
``.opencode/permissions.jsonc`` against the real repository layout:

- the default is no read / no write;
- the human-only files are present and read-only;
- every ``readWrite`` pattern resolves to at least one tracked path;
- the builder role covers the same build surface;
- safety-critical paths carry the ``requiresArchitectureDecision`` guard.

It is a structural check. It does not prove that an agent session obeyed the
model; that is the human review recorded in ``docs/review-memo.md``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PERMISSIONS = ROOT / ".opencode" / "permissions.jsonc"

HUMAN_ONLY = [
    "AGENTS.md",
    "Prompt.md",
    ".opencode/rules.md",
    ".agent/rules.md",
    "architecture-blueprint.md",
]
SAFETY_PATHS = [
    "src/tradingagents/agents/rating.py",
    "src/tradingagents/graph/**",
    "src/tradingagents/risk_gate/**",
    ".github/workflows/**",
]


def _strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments while preserving string contents."""
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        char = text[i]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue
        if char == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        if char == "/" and i + 1 < len(text) and text[i + 1] == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _resolve(pattern: str) -> bool:
    """Whether a permission pattern matches at least one path in the repo."""
    if any(token in pattern for token in ("secrets", "*.pem", "*.key")) or pattern.startswith(".env"):
        return True  # deny/read-only patterns are not expected to exist
    return any(ROOT.glob(pattern))


def check(permissions_path: Path = PERMISSIONS) -> list[str]:
    """Return a list of problems; empty means the model is consistent."""
    if not permissions_path.exists():
        return [f"missing permission model: {permissions_path}"]
    try:
        data = json.loads(_strip_jsonc(permissions_path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        return [f"permission model is not valid JSONC: {exc}"]

    problems: list[str] = []
    default = data.get("default", {})
    if default.get("read") is not False or default.get("write") is not False:
        problems.append("default must deny both read and write")

    read_only = data.get("readOnly") or []
    for name in HUMAN_ONLY:
        if name not in read_only:
            problems.append(f"human-only file missing from readOnly: {name}")
        if not (ROOT / name).exists():
            problems.append(f"human-only file does not exist: {name}")

    read_write = data.get("readWrite") or []
    for pattern in read_write:
        if not _resolve(pattern):
            problems.append(f"readWrite pattern resolves to no path: {pattern}")

    builder = (data.get("roles") or {}).get("builder", {}).get("write") or []
    for pattern in read_write:
        if pattern not in builder:
            problems.append(f"builder role does not cover readWrite pattern: {pattern}")

    guard = data.get("guard") or {}
    guarded = set(guard.get("requiresArchitectureDecision") or [])
    for pattern in SAFETY_PATHS:
        if pattern not in guarded:
            problems.append(f"safety path missing from architecture-decision guard: {pattern}")
    human_guard = set(guard.get("humanOnly") or [])
    for name in HUMAN_ONLY:
        if name not in human_guard:
            problems.append(f"human-only file missing from guard: {name}")

    return problems


def main() -> int:
    problems = check()
    if problems:
        print("FAIL: gate 2 (permissions)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("PASS: gate 2 (permissions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
