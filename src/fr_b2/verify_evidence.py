"""Compare saved evidence bytes with the SHA-256 registry recorded after capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def verify_manifest(manifest_path: Path) -> list[dict[str, str | None]]:
    """Return one integrity result per registered file; paths are manifest-relative."""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("algorithm") != "sha256":
        raise ValueError("manifest algorithm must be sha256")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest must contain a non-empty files list")

    results = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each manifest entry must be an object")
        relative_path = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("each entry must have a non-empty path")
        if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            raise ValueError(f"invalid SHA-256 digest for {relative_path}")

        path = manifest_path.parent / relative_path
        actual = None
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            status = "OK" if actual == expected else "MISMATCH"
        except FileNotFoundError:
            status = "MISSING"
        except OSError:
            status = "UNREADABLE"
        results.append({
            "path": relative_path,
            "status": status,
            "expected_sha256": expected,
            "actual_sha256": actual,
        })
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        results = verify_manifest(args.manifest)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for result in results:
        print(f"{result['status']} {result['path']}")
    return 0 if all(result["status"] == "OK" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
