"""FR-B2: report-conclusion citation check (standalone, offline).

Given a report, a source table and a claims list, decide for each claim whether
its citation can be traced to the original text in the cited evidence. A claim is
SUPPORTED only when every reference resolves; otherwise it is UNTRACEABLE and is
excluded from the ``supported`` count.

Failure reasons (all UNTRACEABLE):
  * claim_not_found      - the claim text cannot be found in the report
  * missing_citation     - the claim has no citation
  * malformed_citation   - the citation is malformed (bad/missing fields)
  * unknown_source       - source_id is not in the source table
  * missing_evidence     - the cited evidence file does not exist
  * unreadable_evidence  - the evidence file exists but cannot be read/decoded
                           (e.g. not valid UTF-8); isolated to that claim
  * invalid_locator      - the cited line is out of range or does not contain
                           the expected snippet

CLI (run from the workspace root, softnew/):

    python -m fr_b2.check_citations \
        --report evidence/AAPL_2026-11-11/report/1_analysts/market.md \
        --sources fr_b2/sources.json \
        --claims fr_b2/claims.example.json \
        --out fr_b2/out/result.json

Only the Python standard library is used, so this runs without TradingAgents
installed and without network access.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SUPPORTED = "SUPPORTED"
UNTRACEABLE = "UNTRACEABLE"

# Reason codes in the order they are checked.
REASONS = (
    "claim_not_found",
    "missing_citation",
    "malformed_citation",
    "unknown_source",
    "missing_evidence",
    "unreadable_evidence",
    "invalid_locator",
)


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_lines(path: Path) -> list[str] | None:
    """Return the file's lines (1-based indexing handled by callers), or None if absent."""
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").splitlines()


def _read_lines_status(path: Path):
    """Read a path as UTF-8 lines; classify the outcome without raising.

    Returns ``(lines, None)`` on success, ``(None, "missing_evidence")`` when the
    file does not exist, and ``(None, "unreadable_evidence")`` when it exists but
    cannot be read or decoded.
    """
    if not path.is_file():
        return None, "missing_evidence"
    try:
        return path.read_text(encoding="utf-8").splitlines(), None
    except (OSError, UnicodeDecodeError):
        return None, "unreadable_evidence"


def _result(claim_id, status, reason=None, *, location=None, detail=None):
    return {
        "id": claim_id,
        "status": status,
        "reason": reason,
        "location": location,
        "detail": detail,
    }


def check_claim(claim: dict, *, report_lines: list[str], report_path: Path,
                sources: dict, base_dir: Path) -> dict:
    """Check a single claim; return a result dict."""
    claim_id = claim.get("id", "<no-id>")

    # 1) Locate the claim text in the report using report_span (line + snippet).
    span = claim.get("report_span")
    if not isinstance(span, dict):
        return _result(claim_id, UNTRACEABLE, "claim_not_found",
                       detail="report_span missing or not an object")
    span_line = span.get("line")
    span_snippet = span.get("snippet")
    if not isinstance(span_line, int) or isinstance(span_line, bool):
        return _result(claim_id, UNTRACEABLE, "claim_not_found",
                       detail=f"report_span.line={span_line!r} is not an integer")
    if span_line < 1 or span_line > len(report_lines):
        return _result(claim_id, UNTRACEABLE, "claim_not_found",
                       detail=f"report_span.line={span_line!r} outside report "
                              f"(1..{len(report_lines)})")
    if not isinstance(span_snippet, str) or not span_snippet.strip():
        return _result(claim_id, UNTRACEABLE, "claim_not_found",
                       detail="report_span.snippet missing or empty; a bare line "
                              "number is not enough to locate the claim")
    report_line_text = report_lines[span_line - 1]
    if span_snippet not in report_line_text:
        return _result(claim_id, UNTRACEABLE, "claim_not_found",
                       detail=f"report line {span_line} does not contain claim snippet")

    claim_location = {
        "report_file": str(report_path),
        "report_line": span_line,
        "report_snippet": report_line_text.strip(),
    }

    # 2) Require a citation.
    citation = claim.get("citation")
    if citation is None:
        return _result(claim_id, UNTRACEABLE, "missing_citation",
                       location=claim_location, detail="claim has no citation object")

    # 3) Validate citation shape.
    if not isinstance(citation, dict):
        return _result(claim_id, UNTRACEABLE, "malformed_citation",
                       location=claim_location, detail="citation is not an object")
    source_id = citation.get("source_id")
    source_line = citation.get("source_line")
    expected_snippet = citation.get("expected_snippet")
    problems = []
    if not isinstance(source_id, str) or not source_id:
        problems.append("source_id must be a non-empty string")
    if not isinstance(source_line, int) or isinstance(source_line, bool):
        problems.append("source_line must be an integer")
    if not isinstance(expected_snippet, str) or not expected_snippet:
        problems.append("expected_snippet must be a non-empty string")
    if problems:
        return _result(claim_id, UNTRACEABLE, "malformed_citation",
                       location=claim_location, detail="; ".join(problems))

    # 4) Resolve the source against the source table.
    entry = (sources or {}).get(source_id)
    if entry is None:
        return _result(claim_id, UNTRACEABLE, "unknown_source",
                       location=claim_location,
                       detail=f"source_id {source_id!r} not in source table")
    source_rel = entry.get("file") if isinstance(entry, dict) else None
    if not source_rel:
        return _result(claim_id, UNTRACEABLE, "malformed_citation",
                       location=claim_location,
                       detail=f"source {source_id!r} has no file path")

    # 5) Evidence must exist and be readable; a single bad file fails only
    #    this claim, never the whole batch.
    source_path = Path(base_dir) / source_rel
    source_lines, read_error = _read_lines_status(source_path)
    if read_error == "missing_evidence":
        return _result(claim_id, UNTRACEABLE, "missing_evidence",
                       location={**claim_location, "source_id": source_id,
                                 "source_file": str(source_path)},
                       detail=f"evidence file not found: {source_rel}")
    if read_error == "unreadable_evidence":
        return _result(claim_id, UNTRACEABLE, "unreadable_evidence",
                       location={**claim_location, "source_id": source_id,
                                 "source_file": str(source_path)},
                       detail=f"evidence file not readable as UTF-8: {source_rel}")

    # 6) The cited line must exist and contain the expected snippet.
    if source_line < 1 or source_line > len(source_lines):
        return _result(claim_id, UNTRACEABLE, "invalid_locator",
                       location={**claim_location, "source_id": source_id,
                                 "source_file": str(source_path), "source_line": source_line},
                       detail=f"source_line {source_line} outside evidence "
                              f"(1..{len(source_lines)})")
    source_line_text = source_lines[source_line - 1]
    if expected_snippet not in source_line_text:
        return _result(claim_id, UNTRACEABLE, "invalid_locator",
                       location={**claim_location, "source_id": source_id,
                                 "source_file": str(source_path), "source_line": source_line},
                       detail=f"source line {source_line} does not contain expected_snippet")

    # All checks passed.
    location = {
        **claim_location,
        "source_id": source_id,
        "source_file": str(source_path),
        "source_line": source_line,
        "source_snippet": source_line_text.strip(),
    }
    return _result(claim_id, SUPPORTED, None, location=location)


def run_check(*, report_path, sources_path, claims_path, base_dir=None) -> dict:
    """Run the full check; return {"summary": {...}, "results": [...]}."""
    base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
    report_path = Path(report_path)
    report_lines = _read_lines(report_path)
    if report_lines is None:
        raise FileNotFoundError(f"report not found: {report_path}")

    sources = _load_json(Path(sources_path)).get("sources", {})
    claims = _load_json(Path(claims_path)).get("claims", [])

    results = [
        check_claim(claim, report_lines=report_lines, report_path=report_path,
                    sources=sources, base_dir=base_dir)
        for claim in claims
    ]

    total = len(results)
    supported = sum(1 for r in results if r["status"] == SUPPORTED)
    untraceable = sum(1 for r in results if r["status"] == UNTRACEABLE)
    summary = {"total": total, "supported": supported, "untraceable": untraceable}
    return {"summary": summary, "results": results}


def render_human(result: dict) -> str:
    """A readable table plus per-claim detail."""
    lines = ["FR-B2 citation check", ""]
    for item in result["results"]:
        loc = item.get("location") or {}
        where = ""
        if loc.get("source_file"):
            where = f" -> {loc['source_file']}:{loc.get('source_line')}"
        status = item["status"]
        reason = f" ({item['reason']})" if item["reason"] else ""
        lines.append(f"- {item['id']}: {status}{reason}{where}")
        if item.get("detail"):
            lines.append(f"    detail: {item['detail']}")
        if item["status"] == SUPPORTED:
            lines.append(f"    report: {loc['report_file']}:{loc['report_line']}")
            lines.append(f"    source: {loc['source_snippet']}")
    s = result["summary"]
    lines += ["", f"SUMMARY total={s['total']} supported={s['supported']} "
                  f"untraceable={s['untraceable']}"]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FR-B2 report-conclusion citation check")
    parser.add_argument("--report", required=True, help="path to the report markdown")
    parser.add_argument("--sources", required=True, help="path to the source table JSON")
    parser.add_argument("--claims", required=True, help="path to the claims list JSON")
    parser.add_argument("--base-dir", default=".", help="base dir for relative evidence paths")
    parser.add_argument("--out", default=None, help="write JSON result to this path")
    args = parser.parse_args(argv)

    # Refuse to overwrite an input: --out must not point at any input file,
    # including evidence files registered in the source table (resolved against
    # --base-dir, the same way the checker resolves them).
    if args.out:
        out_path = Path(args.out).resolve()
        inputs = {
            "report": Path(args.report).resolve(),
            "sources": Path(args.sources).resolve(),
            "claims": Path(args.claims).resolve(),
        }
        base_dir = Path(args.base_dir)
        try:
            sources = _load_json(Path(args.sources)).get("sources", {})
        except (OSError, ValueError):
            sources = {}
        for source_id, entry in (sources or {}).items():
            rel = entry.get("file") if isinstance(entry, dict) else None
            if rel:
                inputs[f"evidence {source_id}"] = (base_dir / rel).resolve()
        for name, input_path in inputs.items():
            if out_path == input_path:
                print(f"error: --out must not overwrite the {name} input "
                      f"({input_path})", file=sys.stderr)
                return 2

    result = run_check(
        report_path=args.report,
        sources_path=args.sources,
        claims_path=args.claims,
        base_dir=args.base_dir,
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(render_human(result))
    s = result["summary"]
    return 0 if s["untraceable"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
