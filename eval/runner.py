"""Offline runner: run one golden case through the graph and record a manifest.

Uses ``graph.stream_run`` rather than ``propagate``: ``propagate`` does not put
the callbacks into the graph config, so tool events and token usage would be
lost there. Streaming also lets us read each ``ToolMessage`` as it happens, which
is the authoritative tool-call count (it is independent of the callback path).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from cli.stats_handler import StatsCallbackHandler
from tradingagents.agents.rating import run_rating
from tradingagents.graph.trading_graph import TradingAgentsGraph

from .golden import GoldenCase
from .manifest import build_manifest
from .sources import EvalContext


@dataclass
class CaseResult:
    case: GoldenCase
    final_state: dict
    rating: str
    manifest: dict
    tool_events: list[dict] = field(default_factory=list)
    output_paths: dict = field(default_factory=dict)


def _new_run_id() -> str:
    """A run id stamped once per run_case, so two runs never share output."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def _config_hash(config: dict) -> str:
    """Stable hash of the config values that shape a run (paths excluded)."""
    stable = {k: v for k, v in config.items()
              if k not in ("results_dir", "data_cache_dir", "memory_log_path")}
    blob = json.dumps(stable, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def run_case(case: GoldenCase, ctx: EvalContext, config: dict, run_id: str | None = None) -> CaseResult:
    run_id = run_id or _new_run_id()
    # Give this run its own results_dir and memory log, both under the run's
    # directory. A shared results_dir would let runs overwrite one state log,
    # and a shared memory log would feed one run's decision into the next.
    work_dir = Path(config["results_dir"]) / "eval" / run_id
    run_config = {
        **config,
        "results_dir": str(work_dir),
        "memory_log_path": str(work_dir / "memory.md"),
    }
    with ctx.activate():
        stats = StatsCallbackHandler()
        graph = TradingAgentsGraph(
            case.analysts, debug=False, config=run_config, callbacks=[stats],
        )
        init_state = graph.create_run_state(
            case.ticker, case.trade_date, case.asset_type, case.portfolio,
        )
        # Pass the handler into the graph config too: propagate() would drop it,
        # but stream_run forwards config, so tool callbacks fire here.
        args = graph.propagator.get_graph_args(callbacks=[stats])

        trace: list[dict] = []
        tool_events: list[dict] = []

        started = time.monotonic()
        for messages, chunk in graph.stream_run(init_state, **args):
            for msg in messages:
                # An AIMessage carries the model's requested tool calls *before*
                # the tool runs. Recording its args is what proves the graph fed
                # this case's ticker/date to the tools, not just the fixture.
                if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        tool_events.append({
                            "name": tc.get("name"),
                            "id": tc.get("id"),
                            "status": "requested",
                            "args": dict(tc.get("args") or {}),
                        })
                elif isinstance(msg, ToolMessage):
                    tool_events.append({
                        "name": getattr(msg, "name", None),
                        "id": getattr(msg, "tool_call_id", None),
                        "status": "ok",
                        "content_len": len(msg.content or ""),
                    })
            if chunk is not None:
                trace.append(chunk)
        elapsed = time.monotonic() - started

        final_state: dict = {}
        for chunk in trace:
            final_state.update(chunk)

        rating = run_rating(final_state)

        # A complete run records its state log and its decision; stream_run does
        # neither, so call what propagate() would have called.
        graph.record_decision(case.ticker, case.trade_date, final_state)

        # Reports go under the run's own directory so runs never collide.
        out_dir = work_dir / case.case_id
        report_file = graph.save_reports(final_state, case.ticker, out_dir, html=True)
        state_log = (work_dir / case.ticker
                     / "TradingAgentsStrategy_logs" / f"full_states_log_{case.trade_date}.json")

        output_paths = {
            "run_id": run_id,
            "report_dir": str(out_dir),
            "complete_report_md": str(report_file),
            "complete_report_html": str(out_dir / "complete_report.html"),
            "state_log": str(state_log),
            "memory_log": str(run_config["memory_log_path"]),
        }

        manifest = build_manifest(
            case=case,
            graph=graph,
            rating=rating,
            config=run_config,
            ctx=ctx,
            tool_events=tool_events,
            tokens=stats.get_stats(),
            latency_s=elapsed,
            output_paths=output_paths,
            config_hash=_config_hash(config),
            run_id=run_id,
        )

        manifest_file = out_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        return CaseResult(
            case=case, final_state=final_state, rating=rating,
            manifest=manifest, tool_events=tool_events, output_paths=output_paths,
        )


def run_suite(cases: list[GoldenCase],
              ctx: EvalContext | Callable[[GoldenCase], EvalContext],
              config: dict, runs: int = 3) -> list[CaseResult]:
    """Run every case ``runs`` times, each run fully isolated.

    ``ctx`` may be a factory ``ctx(case) -> EvalContext`` so fixtures can be
    built per case (ticker/date-aware), or a single ``EvalContext`` -- but a
    single context is only valid for a single case. Reusing one context across
    several cases would feed one case's ticker/date fixtures into every case,
    so the run would silently analyse the wrong instrument; that is rejected
    rather than run. For multiple cases, pass a factory.

    ``run_case`` isolates a run's ``results_dir`` and memory log under a fresh
    ``run_id``.
    """
    if not callable(ctx) and len(cases) > 1:
        raise ValueError(
            "run_suite with multiple cases needs a factory ctx(case) -> "
            "EvalContext; a single EvalContext would reuse one case's fixtures "
            "for every case"
        )
    results: list[CaseResult] = []
    for case in cases:
        for _ in range(runs):
            run_ctx = ctx(case) if callable(ctx) else ctx
            results.append(run_case(case, run_ctx, config))
    return results
