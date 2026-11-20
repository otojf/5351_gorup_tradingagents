"""Six CI blocking gates: local scripts + bad-input self-tests.

These tests exercise the gate scripts in ``scripts/ci/`` directly. They must not
recurse: the regression gate runs ``pytest -q``, so this file never invokes that
gate's subprocess (it is monkeypatched to a fast pass). The pure check functions
are tested against the real repo (expect no problems) and against deliberately
bad inputs (expect problems).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "ci"
for _p in (str(ROOT), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Gate 1: test-approval
# ---------------------------------------------------------------------------


def test_gate1_bad_input_missing_record(tmp_path):
    from check_test_approval import check_record

    problems = check_record(tmp_path / "nope.md")
    assert problems and "missing" in problems[0]


def test_gate1_bad_input_todo_placeholder(tmp_path):
    from check_test_approval import check_record

    rec = tmp_path / "test-approval.md"
    rec.write_text(
        "- approved_by: TODO: someone\n"
        "- approved_date: 2026-11-11\n"
        "- test_scope: eval harness\n",
        encoding="utf-8",
    )
    problems = check_record(rec)
    assert any("approved_by" in p and "placeholder" in p for p in problems)


def test_gate1_bad_input_missing_field(tmp_path):
    from check_test_approval import check_record

    rec = tmp_path / "test-approval.md"
    rec.write_text("- approved_by: Alice (123)\n", encoding="utf-8")
    problems = check_record(rec)
    assert any("approved_date" in p for p in problems)
    assert any("test_scope" in p for p in problems)


def test_gate1_complete_record_passes(tmp_path):
    from check_test_approval import check_record

    rec = tmp_path / "test-approval.md"
    rec.write_text(
        "- approved_by: Alice (123)\n"
        "- approved_date: 2026-11-11\n"
        "- test_scope: tests/test_eval_harness.py\n",
        encoding="utf-8",
    )
    assert check_record(rec) == []


# ---------------------------------------------------------------------------
# Gate 3: schema
# ---------------------------------------------------------------------------


def test_gate3_real_repo_validates():
    from check_schema import validate

    assert validate() == []


def test_gate3_bad_input_missing_field(tmp_path):
    import json

    import yaml
    from check_schema import validate

    schema = json.loads((ROOT / "docs/req/req-schema.json").read_text(encoding="utf-8"))
    registry = yaml.safe_load((ROOT / "docs/req/requirements.yaml").read_text(encoding="utf-8"))
    # Drop fit_criterion from the NFR-E1 nested FR-E1 entry.
    for r in registry["requirements"]:
        if r["id"] == "NFR-E1":
            for s in r["supporting_requirements"]:
                if s["id"] == "FR-E1":
                    del s["fit_criterion"]

    bad_schema = tmp_path / "req-schema.json"
    bad_schema.write_text(json.dumps(schema), encoding="utf-8")
    bad_registry = tmp_path / "requirements.yaml"
    bad_registry.write_text(yaml.safe_dump(registry, allow_unicode=True), encoding="utf-8")

    problems = validate(bad_schema, bad_registry)
    assert problems, "schema gate must reject a registry missing fit_criterion"


# ---------------------------------------------------------------------------
# Gate 6: AI-use log
# ---------------------------------------------------------------------------


def test_gate6_real_repo_covers_eval_change():
    from check_ai_use_log import check

    # The eval change is listed in the AI-use log.
    assert check(["eval/runner.py"]) == []


def test_gate6_bad_input_missing_entry():
    from check_ai_use_log import check

    # A path no log entry names and no listed parent covers.
    problems = check(["tradingagents/brand_new_module.py"])
    assert problems and "not covered" in problems[0]


def test_gate6_docs_only_change_is_fine():
    from check_ai_use_log import check

    assert check(["docs/req/requirements.yaml"]) == []


def test_gate6_missing_log(tmp_path):
    from check_ai_use_log import check

    problems = check(["eval/runner.py"], log_path=tmp_path / "nope.yaml")
    assert problems and "missing" in problems[0]


# ---------------------------------------------------------------------------
# Gate 2 / 4 / 5: subprocess scripts
# ---------------------------------------------------------------------------


def test_gate2_static_analysis_runs_and_reports_uncovered():
    """Run the real static-analysis script; it must exit 0 and name the gaps."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_static_analysis.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NOT covered" in proc.stdout or "NOT COVERED" in proc.stdout


def test_gate4_semantic_eval_mocked_pass(monkeypatch):
    import check_semantic_eval

    class _P:
        returncode = 0
        stdout = "21 passed"
        stderr = ""

    monkeypatch.setattr(check_semantic_eval.subprocess, "run", lambda *a, **k: _P())
    assert check_semantic_eval.main() == 0


def test_gate4_semantic_eval_mocked_fail(monkeypatch):
    import check_semantic_eval

    class _P:
        returncode = 1
        stdout = "1 failed"
        stderr = ""

    monkeypatch.setattr(check_semantic_eval.subprocess, "run", lambda *a, **k: _P())
    assert check_semantic_eval.main() == 1


def test_gate5_regression_mocked_pass(monkeypatch):
    """Regression gate script logic only; never run pytest inside pytest."""
    import check_regression

    class _P:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(check_regression.subprocess, "run", lambda *a, **k: _P())
    assert check_regression.main() == 0


def test_gate5_regression_mocked_fail(monkeypatch):
    import check_regression

    class _P:
        returncode = 2
        stdout = "errors"
        stderr = ""

    monkeypatch.setattr(check_regression.subprocess, "run", lambda *a, **k: _P())
    assert check_regression.main() == 1


@pytest.mark.unit
def test_gate_scripts_importable_and_have_main():
    """Every gate script exposes a callable main()."""
    for name in (
        "check_test_approval",
        "check_schema",
        "check_ai_use_log",
        "check_static_analysis",
        "check_semantic_eval",
        "check_regression",
    ):
        module = __import__(name)
        assert callable(module.main), name
