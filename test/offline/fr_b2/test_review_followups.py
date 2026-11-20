"""PR #11 review follow-ups for FR-B2 evidence integrity and exit semantics."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fr_b2 import check_citations

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/evidence/fr-b2"
MANIFEST = EVIDENCE / "evidence-sha256.json"


def test_registered_evidence_hashes_match():
    from fr_b2.verify_evidence import verify_manifest

    registered = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected_paths = {
        path.relative_to(EVIDENCE).as_posix()
        for path in (EVIDENCE / "evidence/AAPL_2026-11-11").rglob("*")
        if path.is_file()
    }
    assert {entry["path"] for entry in registered["files"]} == expected_paths
    results = verify_manifest(MANIFEST)
    assert len(results) == len(expected_paths) > 0
    assert all(result["status"] == "OK" for result in results)


@pytest.mark.parametrize("change,status", [("modify", "MISMATCH"), ("remove", "MISSING")])
def test_changed_evidence_is_detected(tmp_path, change, status):
    from fr_b2.verify_evidence import verify_manifest

    evidence = tmp_path / "snapshot.txt"
    original = b"AAPL,2026-11-11,355.63\n"
    evidence.write_bytes(original)
    manifest = tmp_path / "hashes.json"
    manifest.write_text(json.dumps({
        "algorithm": "sha256",
        "files": [{"path": evidence.name, "sha256": hashlib.sha256(original).hexdigest()}],
    }), encoding="utf-8")
    if change == "modify":
        evidence.write_bytes(b"AAPL,2026-11-11,1.00\n")
    else:
        evidence.unlink()

    assert verify_manifest(manifest)[0]["status"] == status


def test_integrity_cli_reports_success_and_changed_evidence(tmp_path):
    evidence = tmp_path / "snapshot.txt"
    original = b"verified quotation\n"
    evidence.write_bytes(original)
    manifest = tmp_path / "hashes.json"
    manifest.write_text(json.dumps({
        "algorithm": "sha256",
        "files": [{"path": evidence.name, "sha256": hashlib.sha256(original).hexdigest()}],
    }), encoding="utf-8")
    command = [sys.executable, "-m", "fr_b2.verify_evidence", "--manifest", str(manifest)]
    valid = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert valid.returncode == 0
    assert "OK snapshot.txt" in valid.stdout

    evidence.write_bytes(b"changed quotation\n")
    changed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert changed.returncode == 1
    assert "MISMATCH snapshot.txt" in changed.stdout


def test_integrity_cli_rejects_invalid_manifest(tmp_path):
    manifest = tmp_path / "hashes.json"
    manifest.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "fr_b2.verify_evidence", "--manifest", str(manifest)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr


def test_completed_citation_check_returns_zero_with_untraceable_results(capsys):
    exit_code = check_citations.main([
        "--report", str(EVIDENCE / "evidence/AAPL_2026-11-11/report/1_analysts/market.md"),
        "--sources", str(ROOT / "src/fr_b2/sources.json"),
        "--claims", str(ROOT / "src/fr_b2/claims.example.json"),
        "--base-dir", str(ROOT),
    ])
    assert exit_code == 0
    assert "SUMMARY total=6 supported=1 untraceable=5" in capsys.readouterr().out
