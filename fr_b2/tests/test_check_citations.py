"""Offline acceptance tests for FR-B2 (report conclusion citation check).

These tests run with no network and no model. They pin the behaviour the
implementation must satisfy:

  * one positive citation resolves to the exact report line and snapshot line;
  * five negatives each report UNTRACEABLE with a distinct reason;
  * the batch summary is total=6, supported=1, untraceable=5;
  * a claim whose text cannot be found in the report returns claim_not_found.

Run from the workspace root (softnew/):

    conda run -n ta-frb2 pytest fr_b2/tests -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fr_b2 import check_citations

WS = Path(__file__).resolve().parents[2]
REPORT = WS / "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/report/1_analysts/market.md"
SNAPSHOT = WS / "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot.txt"
SOURCES = WS / "fr_b2/sources.json"
CLAIMS = WS / "fr_b2/claims.example.json"


@pytest.fixture(scope="module")
def batch():
    return check_citations.run_check(
        report_path=REPORT,
        sources_path=SOURCES,
        claims_path=CLAIMS,
        base_dir=WS,
    )


def _by_id(result):
    return {item["id"]: item for item in result["results"]}


def test_inputs_exist():
    assert REPORT.is_file(), REPORT
    assert SNAPSHOT.is_file(), SNAPSHOT
    assert SOURCES.is_file(), SOURCES
    assert CLAIMS.is_file(), CLAIMS


def test_source_table_shape():
    table = json.loads(SOURCES.read_text(encoding="utf-8"))
    assert set(table["sources"]) >= {"S1", "S2"}
    assert table["sources"]["S1"]["file"] == "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot.txt"
    assert "S999" not in table["sources"]


def test_positive_resolves_to_report_and_snapshot(batch):
    item = _by_id(batch)["c1_valid"]
    assert item["status"] == "SUPPORTED"
    assert item["reason"] is None
    loc = item["location"]
    assert loc["report_file"].endswith("market.md")
    assert loc["report_line"] == 5
    assert loc["source_file"].endswith("snapshot.txt")
    assert loc["source_line"] == 66
    assert "355.63" in loc["source_snippet"]


def test_five_negatives_each_have_expected_reason(batch):
    items = _by_id(batch)
    expected = {
        "c2_missing_citation": "missing_citation",
        "c3_malformed_citation": "malformed_citation",
        "c4_unknown_source": "unknown_source",
        "c5_missing_evidence": "missing_evidence",
        "c6_invalid_locator": "invalid_locator",
    }
    for claim_id, reason in expected.items():
        item = items[claim_id]
        assert item["status"] == "UNTRACEABLE", claim_id
        assert item["reason"] == reason, claim_id


def test_missing_evidence_file_is_separate_from_positive(batch):
    items = _by_id(batch)
    # The positive sample uses S1 and must stay readable...
    assert items["c1_valid"]["status"] == "SUPPORTED"
    assert SNAPSHOT.is_file()
    # ...while the missing-evidence sample points at a distinct absent file.
    assert items["c5_missing_evidence"]["reason"] == "missing_evidence"
    assert not (WS / "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot_MISSING.txt").is_file()


def test_summary_counts(batch):
    summary = batch["summary"]
    assert summary["total"] == 6
    assert summary["supported"] == 1
    assert summary["untraceable"] == 5
    # supported is exactly the set of SUPPORTED results, never the negatives.
    supported_ids = [r["id"] for r in batch["results"] if r["status"] == "SUPPORTED"]
    assert supported_ids == ["c1_valid"]


def test_negatives_never_count_as_supported(batch):
    for item in batch["results"]:
        if item["status"] != "SUPPORTED":
            assert item["status"] == "UNTRACEABLE"


def test_claim_not_found(tmp_path):
    """Independent check: a report_span that is not in the report fails as claim_not_found."""
    claims = {
        "claims": [
            {
                "id": "c_not_found",
                "report_span": {"line": 5, "snippet": "AAPL closed at 123.45 on 1999-01-01"},
                "citation": {
                    "source_id": "S1",
                    "source_line": 66,
                    "expected_snippet": "| 2026-11-11 | 355.63 |",
                },
            }
        ]
    }
    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps(claims), encoding="utf-8")

    result = check_citations.run_check(
        report_path=REPORT,
        sources_path=SOURCES,
        claims_path=claims_path,
        base_dir=WS,
    )
    item = result["results"][0]
    assert item["status"] == "UNTRACEABLE"
    assert item["reason"] == "claim_not_found"
    assert result["summary"]["supported"] == 0


# ---------------------------------------------------------------------------
# Regression tests for issues found at review time.
# ---------------------------------------------------------------------------


def _write_claims(tmp_path, claims):
    path = tmp_path / "claims.json"
    path.write_text(json.dumps({"claims": claims}), encoding="utf-8")
    return path


def test_valid_line_without_snippet_is_claim_not_found(tmp_path):
    """Issue 1: a bare valid line number must not be SUPPORTED; no snippet is claim_not_found."""
    good_citation = {
        "source_id": "S1",
        "source_line": 66,
        "expected_snippet": "| 2026-11-11 | 355.63 |",
    }
    claims_path = _write_claims(tmp_path, [
        {"id": "no_snippet", "report_span": {"line": 5}, "citation": good_citation},
        {"id": "empty_snippet", "report_span": {"line": 5, "snippet": ""}, "citation": good_citation},
        {"id": "bad_line", "report_span": {"line": "five", "snippet": "AAPL"}, "citation": good_citation},
        {"id": "missing_span", "citation": good_citation},
    ])
    result = check_citations.run_check(
        report_path=REPORT, sources_path=SOURCES, claims_path=claims_path, base_dir=WS,
    )
    for item in result["results"]:
        assert item["status"] == "UNTRACEABLE", item["id"]
        assert item["reason"] == "claim_not_found", item["id"]
    assert result["summary"]["supported"] == 0


def test_unreadable_evidence_isolated_to_its_claim(tmp_path):
    """Issue 2: one undecodable evidence file fails only its claim; good citations still pass."""
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\xff\xfe\x00 not utf-8 \x80\x81")

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    sources["sources"]["SBAD"] = {"file": str(bad)}
    sources_path = tmp_path / "sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    claims_path = _write_claims(tmp_path, [
        {
            "id": "good",
            "report_span": {"line": 5, "snippet": "AAPL closed at **355.63** on 2026-11-11"},
            "citation": {"source_id": "S1", "source_line": 66,
                         "expected_snippet": "| 2026-11-11 | 355.63 |"},
        },
        {
            "id": "undecodable",
            "report_span": {"line": 5, "snippet": "AAPL closed at **355.63** on 2026-11-11"},
            "citation": {"source_id": "SBAD", "source_line": 1, "expected_snippet": "x"},
        },
    ])
    result = check_citations.run_check(
        report_path=REPORT, sources_path=sources_path, claims_path=claims_path, base_dir=WS,
    )
    items = {r["id"]: r for r in result["results"]}
    assert items["good"]["status"] == "SUPPORTED"
    assert items["undecodable"]["status"] == "UNTRACEABLE"
    assert items["undecodable"]["reason"] == "unreadable_evidence"
    assert result["summary"]["supported"] == 1
    assert result["summary"]["untraceable"] == 1


def test_out_colliding_with_input_is_refused(tmp_path):
    """Issue 3: --out pointing at any input must be refused and leave that file intact."""
    claims_copy = tmp_path / "claims.json"
    claims_copy.write_text(CLAIMS.read_text(encoding="utf-8"), encoding="utf-8")
    original = claims_copy.read_text(encoding="utf-8")

    args = [
        "--report", str(REPORT),
        "--sources", str(SOURCES),
        "--claims", str(claims_copy),
        "--out", str(claims_copy),
    ]
    rc = check_citations.main(args)
    assert rc != 0
    # The input file must be untouched.
    assert claims_copy.read_text(encoding="utf-8") == original


def test_out_colliding_with_evidence_file_is_refused(tmp_path):
    """Issue (follow-up): --out must also refuse to clobber an evidence file
    registered in the source table, resolved via --base-dir."""
    # A temporary copy of the real snapshot, registered in a temp source table.
    snap_copy = tmp_path / "snapshot.txt"
    snap_copy.write_bytes(SNAPSHOT.read_bytes())
    original_bytes = snap_copy.read_bytes()

    sources = {
        "sources": {
            "S1": {"file": "snapshot.txt", "description": "temp copy of snapshot"},
        }
    }
    sources_path = tmp_path / "sources.json"
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    claims = {
        "claims": [
            {
                "id": "c1_valid",
                "report_span": {"line": 5, "snippet": "AAPL closed at **355.63** on 2026-11-11"},
                "citation": {"source_id": "S1", "source_line": 66,
                             "expected_snippet": "| 2026-11-11 | 355.63 |"},
            }
        ]
    }
    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps(claims), encoding="utf-8")

    args = [
        "--report", str(REPORT),
        "--sources", str(sources_path),
        "--claims", str(claims_path),
        "--base-dir", str(tmp_path),
        "--out", str(snap_copy),
    ]
    rc = check_citations.main(args)
    assert rc == 2
    # The evidence file must be byte-for-byte unchanged (not overwritten by JSON).
    assert snap_copy.read_bytes() == original_bytes
    assert snap_copy.read_bytes().startswith(b"## Verified market data snapshot")
