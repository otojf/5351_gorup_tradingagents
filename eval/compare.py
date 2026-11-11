"""Before/after comparison: two suites in, a CSV and a Markdown table out.

The two sides must be semantically different runs (for example four analysts vs
three, or free-text vs structured), not the same fixtures copied. The table
shows each case's rating, token, latency and tool-count on both sides, plus the
deltas, so a real difference is visible.
"""

from __future__ import annotations

import csv
from pathlib import Path

_COLUMNS = (
    "case_id",
    "before_rating",
    "after_rating",
    "rating_changed",
    "before_tokens",
    "after_tokens",
    "token_delta_pct",
    "before_latency_s",
    "after_latency_s",
    "before_tool_calls",
    "after_tool_calls",
)


def _total_tokens(manifest: dict) -> int:
    tokens = manifest.get("tokens") or {}
    return int(tokens.get("in", 0)) + int(tokens.get("out", 0))


def _delta_pct(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return round((after - before) / before * 100.0, 2)


def _rows(before, after) -> list[dict]:
    by_case_after = {r.case.case_id: r for r in after}
    rows = []
    for b in before:
        a = by_case_after.get(b.case.case_id)
        if a is None:
            continue
        bt, at = _total_tokens(b.manifest), _total_tokens(a.manifest)
        rows.append({
            "case_id": b.case.case_id,
            "before_rating": b.rating,
            "after_rating": a.rating,
            "rating_changed": b.rating != a.rating,
            "before_tokens": bt,
            "after_tokens": at,
            "token_delta_pct": _delta_pct(bt, at),
            "before_latency_s": b.manifest.get("latency_s"),
            "after_latency_s": a.manifest.get("latency_s"),
            "before_tool_calls": b.manifest.get("tool_calls_total"),
            "after_tool_calls": a.manifest.get("tool_calls_total"),
        })
    return rows


def compare(before: list, after: list, out_dir) -> dict:
    """Write ``compare.csv`` and ``compare.md`` under ``out_dir``; return the rows."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _rows(before, after)

    csv_path = out_dir / "compare.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    md_path = out_dir / "compare.md"
    header = "| " + " | ".join(_COLUMNS) + " |"
    sep = "| " + " | ".join(["---"] * len(_COLUMNS)) + " |"
    lines = ["# Before/after comparison", "", header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row[c]) for c in _COLUMNS) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"rows": rows, "csv": str(csv_path), "md": str(md_path)}
