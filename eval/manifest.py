"""Run manifest: what produced a run, for comparing runs and auditing them.

Fields required by ``requirements.yaml`` NFR-E1 are present. Ones the baseline
cannot yet supply (degradations, risk verdicts, traceability) are recorded as
``None`` with a reason in ``unavailable_sources``, rather than faked.
"""

from __future__ import annotations

import subprocess

from .golden import GoldenCase


def _git_commit() -> str | None:
    """The checked-out commit, or None when git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def build_manifest(*, case: GoldenCase, graph, rating: str, config: dict,
                   ctx, tool_events: list[dict], tokens: dict,
                   latency_s: float, output_paths: dict, config_hash: str,
                   run_id: str) -> dict:
    settings = graph.run_settings()

    token_record = {
        "in": tokens.get("tokens_in", 0),
        "out": tokens.get("tokens_out", 0),
        "llm_calls": tokens.get("llm_calls", 0),
        "tool_calls": tokens.get("tool_calls", 0),
    }

    # ``tool_events`` holds two kinds of record for the same call: the AIMessage
    # "requested" entry (with args) and the ToolMessage "ok" entry (with
    # content_len). The executed count is the finished ToolMessages only, which
    # must match the callback handler's on_tool_start count.
    tool_calls_total = sum(1 for e in tool_events if e.get("status") == "ok")
    tool_call_requests_total = sum(
        1 for e in tool_events if e.get("status") == "requested"
    )

    return {
        "harness_version": "slice1",
        "run_id": run_id,
        "case_id": case.case_id,
        "ticker": case.ticker,
        "trade_date": case.trade_date,
        "asset_type": case.asset_type,
        "analysts": list(case.analysts),
        "rating": rating,
        # From run_settings() (allowlisted); model/provider are always available.
        "model": {
            "deep_think_llm": settings.get("deep_think_llm"),
            "quick_think_llm": settings.get("quick_think_llm"),
            "deep_think_provider": settings.get("deep_think_provider"),
            "quick_think_provider": settings.get("quick_think_provider"),
        },
        "commit": _git_commit(),
        "config_hash": config_hash,
        "prompt_snapshot": ctx.llm.snapshot_id(),
        "data_snapshot": ctx.source.snapshot_id(),
        "tokens": token_record,
        "latency_s": round(latency_s, 4),
        "degradations": None,
        "risk_verdicts": None,
        "traceability": None,
        "tool_calls_total": tool_calls_total,
        "tool_call_requests_total": tool_call_requests_total,
        "tool_calls": tool_events,
        "output_paths": output_paths,
        # Why a required-but-unavailable field is null. This is the honest
        # boundary: the baseline has no structured event for these yet.
        "unavailable_sources": {
            "degradations": "structured.py logs only; no DEGRADED event in state",
            "risk_verdicts": "risk gate not implemented in baseline",
            "traceability": "EvidenceRef not implemented in baseline",
        },
        # What this manifest does and does not prove.
        "scope_note": (
            "Proves the harness and graph structure are deterministic under a "
            "fixed scripted source. Does not prove real-input reproducibility."
        ),
    }
