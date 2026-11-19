#!/usr/bin/env python3
"""Gate 3: schema.

The requirements registry must validate against its JSON schema (course D7,
gate 3). This is a structural check: every entry has the required fields and
types; it does not judge the semantic quality of a criterion.

Usage::

    python scripts/ci/check_schema.py

Exit 0 = registry validates; exit 1 = validation errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

SCHEMA_PATH = Path("docs/req/req-schema.json")
REGISTRY_PATH = Path("docs/req/requirements.yaml")


def validate(schema_path: Path = SCHEMA_PATH,
             registry_path: Path = REGISTRY_PATH) -> list[str]:
    """Return a list of validation problems; empty means valid."""
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"missing schema: {schema_path}"]
    except json.JSONDecodeError as exc:
        return [f"schema is not valid JSON: {exc}"]

    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"missing registry: {registry_path}"]
    except yaml.YAMLError as exc:
        return [f"registry is not valid YAML: {exc}"]

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" for e in errors]


def main() -> int:
    problems = validate()
    if problems:
        print("FAIL: gate 3 (schema)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASS: gate 3 (schema)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
