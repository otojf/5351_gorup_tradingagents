"""NFR-E1 demo: run the 3-case golden set before/after and write the table.

Offline and deterministic: scripted data + scripted model, no network, no LLM.
The "before" side uses all four analysts; the "after" side drops the sentiment
analyst, so every case shows a real token difference. Outputs land next to this
script (compare.csv / compare.md) and a verbatim capture in demo-output.txt.
"""

from __future__ import annotations

import dataclasses
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.compare import compare  # noqa: E402
from eval.golden import GOLDEN_SET  # noqa: E402
from eval.runner import run_suite  # noqa: E402
from eval.sources import EvalContext, ScriptedLLMSource, ScriptedSource  # noqa: E402
from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402

FOUR = ("market", "social", "news", "fundamentals")
THREE = ("market", "news", "fundamentals")


def _config(tag: str, work_root: Path) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(work_root / tag / "results"),
        data_cache_dir=str(work_root / tag / "cache"),
        memory_log_path=str(work_root / tag / "memory.md"),
    )
    return cfg


def _ctx_factory(case):
    return EvalContext(
        source=ScriptedSource(case.ticker, case.trade_date),
        llm=ScriptedLLMSource(case.ticker, case.trade_date),
    )


def main() -> int:
    before_cases = [dataclasses.replace(c, analysts=FOUR) for c in GOLDEN_SET]
    after_cases = [dataclasses.replace(c, analysts=THREE) for c in GOLDEN_SET]

    # Intermediates (state logs, memory, cache) go to a throwaway dir; only the
    # comparison table and the capture are kept next to this script.
    with tempfile.TemporaryDirectory() as tmp:
        work_root = Path(tmp)
        before = run_suite(before_cases, _ctx_factory, _config("before", work_root), runs=1)
        after = run_suite(after_cases, _ctx_factory, _config("after", work_root), runs=1)
        out = compare(before, after, HERE)

    lines = [
        "# NFR-E1 demo output (scripted, offline)",
        "",
        f"golden cases: {len(GOLDEN_SET)}",
        f"before analysts: {', '.join(FOUR)}",
        f"after analysts:  {', '.join(THREE)}",
        "",
        "case_id  before_rating  after_rating  before_tokens  after_tokens  token_delta_pct",
    ]
    for row in out["rows"]:
        lines.append(
            f"{row['case_id']}  {row['before_rating']}  {row['after_rating']}  "
            f"{row['before_tokens']}  {row['after_tokens']}  {row['token_delta_pct']}"
        )
    lines += ["", f"csv: {Path(out['csv']).name}", f"md:  {Path(out['md']).name}"]
    report = "\n".join(lines) + "\n"
    (HERE / "demo-output.txt").write_text(report, encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
