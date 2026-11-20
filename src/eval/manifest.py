"""Run manifest: what produced a run, for comparing runs and auditing them.

Fields required by ``requirements.yaml`` NFR-E1 are present. ``prompt_hash`` is a
real sha256 of the prompt-template source (see ``eval.sources.prompt_template_hash``);
``prompt_source_id`` labels *which* scripted source produced the run (e.g.
``scripted-llm-v1:NVDA:2026-01-09``) -- it is a source label, not a hash.

Fields owned by other branches (degradations from A, risk verdicts from B,
traceability from D) are injected via ``integrations`` (see
``eval.manifest_rules`` for the interface contract and field shapes). When a
caller supplies nothing they are recorded as ``None`` with a reason in
``unavailable_sources``, rather than faked.
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
                   run_id: str, integrations: dict | None = None) -> dict:
    settings = graph.run_settings()

    # Optional data owned by other branches (A: DEGRADED events, B: risk
    # verdicts, D: evidence traceability). When a caller supplies nothing, the
    # fields stay null with the reason in ``unavailable_sources``. When a caller
    # supplies the normalized dicts, they are recorded verbatim -- the harness
    # does not invent them.
    integrations = integrations or {}
    degradations = integrations.get("degradations")
    risk_verdicts = integrations.get("risk_verdicts")
    traceability = integrations.get("traceability")

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
        "prompt_hash": ctx.llm.prompt_hash(),
        "prompt_source_id": ctx.llm.snapshot_id(),
        "data_snapshot": ctx.source.snapshot_id(),
        "tokens": token_record,
        "latency_s": round(latency_s, 4),
        "degradations": degradations,
        "risk_verdicts": risk_verdicts,
        "traceability": traceability,
        "tool_calls_total": tool_calls_total,
        "tool_call_requests_total": tool_call_requests_total,
        "tool_calls": tool_events,
        "output_paths": output_paths,
        # Why a required-but-unavailable field is null. Only fields this run did
        # not receive are listed here; injected fields are not "unavailable".
        "unavailable_sources": {
            "degradations": None if degradations is not None
            else "structured.py logs only; no DEGRADED event in state",
            "risk_verdicts": None if risk_verdicts is not None
            else "risk gate not implemented in baseline",
            "traceability": None if traceability is not None
            else "EvidenceRef not implemented in baseline",
        },
        # What this manifest does and does not prove.
        "scope_note": (
            "Proves the harness and graph structure are deterministic under a "
            "fixed scripted source. Does not prove real-input reproducibility."
        ),
    }
