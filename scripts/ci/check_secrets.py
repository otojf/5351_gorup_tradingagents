#!/usr/bin/env python3
"""Gate 2 companion: secret scan.

Scans tracked text files for high-confidence credential patterns. This is a
targeted check, not a replacement for a dedicated secret scanner, but it makes
the security part of gate 2 executable and blocks the common accidental
commit: private keys, cloud access keys, provider tokens, and assigned
password/secret values.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".ico",
}
_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("provider API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("assigned secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"]"
        r"[A-Za-z0-9_\-]{20,}['\"]"
    )),
]


def _tracked_files(root: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [root / name for name in out.decode("utf-8").split("\0") if name]


def check(root: Path = ROOT) -> list[str]:
    """Return ``path:line: pattern`` findings; empty means clean."""
    problems: list[str] = []
    for path in _tracked_files(root):
        if path.suffix.lower() in _SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for label, pattern in _PATTERNS:
                if pattern.search(line):
                    problems.append(f"{path.relative_to(root)}:{line_no}: {label}")
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("FAIL: gate 2 (secret scan)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("PASS: gate 2 (secret scan; targeted patterns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
