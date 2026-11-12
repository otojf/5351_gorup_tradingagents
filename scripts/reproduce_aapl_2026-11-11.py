"""Run one AAPL analysis on this TradingAgents checkout and save FR-B2 evidence.

The repository root *is* the TradingAgents source, so no separate upstream
clone is needed. Run from the repository root with .env populated:

    python scripts/reproduce_aapl_2026-11-11.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
# The repo root is the TradingAgents package root (tradingagents/ lives here).
sys.path.insert(0, str(WS))

os.chdir(WS)

import tradingagents  # noqa: E402  (loads .env from cwd)

from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402
from tradingagents.default_config import build_default_config  # noqa: E402
from tradingagents.dataflows.vendors.yahoo.snapshot import (  # noqa: E402
    build_verified_market_snapshot,
)

TICKER = "AAPL"
TRADE_DATE = "2026-11-11"
ANALYSTS = ("market", "social", "news", "fundamentals")

OUT = WS / "docs" / "evidence" / "fr-b2" / "evidence" / f"{TICKER}_{TRADE_DATE}"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    config = build_default_config()
    print("provider   :", config["llm_provider"])
    print("backend_url:", config["backend_url"])
    print("quick/deep :", config["quick_think_llm"], "/", config["deep_think_llm"])
    print("results_dir:", config["results_dir"])
    print("trade_date :", TRADE_DATE)

    # 1) The official verification snapshot, as text (line-addressable), taken
    #    through the same pinned vendor module the agents use.
    snap_text = build_verified_market_snapshot(TICKER, TRADE_DATE, look_back_days=30)
    (OUT / "snapshot.txt").write_text(snap_text, encoding="utf-8")
    print(f"[evidence] snapshot.txt written ({snap_text.count(chr(10)) + 1} lines)")

    # 2) The real analysis.
    ta = TradingAgentsGraph(debug=True, config=config, selected_analysts=ANALYSTS)
    state, decision = ta.propagate(TICKER, TRADE_DATE)

    settings = ta.run_settings()
    report_dir = ta.save_reports(state, TICKER, save_path=OUT / "report", html=True)

    (OUT / "decision.txt").write_text(str(decision), encoding="utf-8")
    (OUT / "run_settings.json").write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Keep the analyst/manager sections as separate evidence files too.
    sections = {
        "market_report": state.get("market_report"),
        "sentiment_report": state.get("sentiment_report"),
        "news_report": state.get("news_report"),
        "fundamentals_report": state.get("fundamentals_report"),
        "investment_plan": state.get("investment_plan"),
        "trader_investment_plan": state.get("trader_investment_plan"),
        "final_trade_decision": state.get("final_trade_decision"),
    }
    for key, val in sections.items():
        if val:
            (OUT / f"{key}.md").write_text(str(val), encoding="utf-8")

    log = {
        "ticker": TICKER,
        "trade_date": TRADE_DATE,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "version": tradingagents.__version__,
        "decision": str(decision),
        "report_dir": str(report_dir),
        "snapshot_method": "独立调用官方 tradingagents.dataflows.vendors.yahoo.snapshot.build_verified_market_snapshot(文本, 行号可定位)",
    }
    (OUT / "run_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== decision ===")
    print(decision)
    print("\n=== report ===")
    print(report_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
