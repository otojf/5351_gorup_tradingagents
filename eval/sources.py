"""Data and LLM sources for the eval harness.

The interfaces are shaped for recording/replay later (``Source``/``LLMSource``
return the data a vendor would, plus a snapshot id). The only implementation in
Slice 1 is scripted: it patches the same points the offline end-to-end test does
(``tests/test_graph_end_to_end.py``), so no production code changes.

What this proves: the harness and the graph structure are deterministic under a
fixed source. It does NOT prove real-input reproducibility; that needs recorded
replay (``FR-E4``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, ExitStack, contextmanager
from typing import Protocol, runtime_checkable

import pandas as pd
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field

from tradingagents.agents import context, schemas
from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.dataflows import router
from tradingagents.dataflows.vendors.yahoo import market as yahoo_market, snapshot

# The scripted model answers every free-text reader with this, and every
# structured reader with the schemas below, so the decision is fixed.
TEXT = "Report.\n\n**Rating**: Overweight\n\nFINAL TRANSACTION PROPOSAL: **BUY**"

STRUCTURED = {
    schemas.ResearchPlan: schemas.ResearchPlan(
        recommendation=schemas.PortfolioRating.OVERWEIGHT, rationale="r", strategic_actions="a"),
    schemas.TraderProposal: schemas.TraderProposal(action=schemas.TraderAction.BUY, reasoning="r"),
    schemas.PortfolioDecision: schemas.PortfolioDecision(
        rating=schemas.PortfolioRating.OVERWEIGHT, executive_summary="s",
        investment_thesis="Structured reasoning."),
    schemas.SentimentReport: schemas.SentimentReport(
        overall_band=schemas.SentimentBand.NEUTRAL, overall_score=5.0, confidence="low", narrative="n"),
}


@runtime_checkable
class Source(Protocol):
    """A data source: vendor responses, the OHLCV frame, a snapshot id, and the
    patch scope that installs them."""

    id: str

    def vendor_responses(self) -> Mapping[str, Callable]: ...

    def ohlcv_frame(self) -> Callable: ...

    def snapshot_id(self) -> str: ...

    def activate(self) -> AbstractContextManager[None]: ...


@runtime_checkable
class LLMSource(Protocol):
    """An LLM source: one chat model per tier, a snapshot id, and its patch scope."""

    id: str

    def chat_model(self, tier: str) -> BaseChatModel: ...

    def snapshot_id(self) -> str: ...

    def activate(self) -> AbstractContextManager[None]: ...


class ScriptedSource:
    """Vendor/data stubs for one case's ticker and date."""

    id = "scripted-data-v1"

    def __init__(self, ticker: str = "NVDA", trade_date: str = "2026-01-09"):
        self.ticker = ticker
        self.trade_date = trade_date

    def vendor_responses(self) -> Mapping[str, Mapping[str, Callable]]:
        """method -> vendor -> stub, for every vendor the router knows.

        This is the data ``activate()`` installs, so the interface and the patch
        are the same thing rather than two parallel definitions.
        """
        return {
            method: {
                vendor: (lambda *a, _m=method, **k: f"{_m} data")
                for vendor in vendors
            }
            for method, vendors in router.VENDOR_METHODS.items()
        }

    def ohlcv_frame(self) -> Callable:
        prices = pd.DataFrame({
            "Date": pd.bdate_range(end=self.trade_date, periods=60),
            "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1_000_000,
        })
        return lambda *a, **k: prices.copy()

    def snapshot_id(self) -> str:
        return f"scripted-data-v1:{self.ticker}:{self.trade_date}"

    @contextmanager
    def activate(self) -> Iterator[None]:
        saved_router = {m: dict(v) for m, v in router.VENDOR_METHODS.items()}
        saved_load = snapshot.load_ohlcv
        saved_ticker = yahoo_market.yf.Ticker
        saved_conf = sentiment_analyst.fetch_stocktwits_messages
        saved_reddit = sentiment_analyst.fetch_reddit_posts
        long_name = self.ticker
        try:
            for method, vendors in self.vendor_responses().items():
                router.VENDOR_METHODS[method].update(vendors)
            snapshot.load_ohlcv = self.ohlcv_frame()
            yahoo_market.yf.Ticker = (
                lambda s: type("T", (), {"info": {"longName": long_name}})())
            sentiment_analyst.fetch_stocktwits_messages = lambda *a, **k: "no posts"
            sentiment_analyst.fetch_reddit_posts = lambda *a, **k: "no posts"
            context._identity.cache_clear()
            yield
        finally:
            for method, vendors in saved_router.items():
                router.VENDOR_METHODS[method].clear()
                router.VENDOR_METHODS[method].update(vendors)
            snapshot.load_ohlcv = saved_load
            yahoo_market.yf.Ticker = saved_ticker
            sentiment_analyst.fetch_stocktwits_messages = saved_conf
            sentiment_analyst.fetch_reddit_posts = saved_reddit
            context._identity.cache_clear()


class ScriptedModel(BaseChatModel):
    """Calls every bound tool once with the case's ticker/date, then answers."""

    structured: bool = False
    tools: tuple = ()
    ticker: str = "NVDA"
    trade_date: str = "2026-01-09"
    calls: list = Field(default_factory=list)
    last_tool_args: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"tools": tuple(tools)})

    def with_structured_output(self, schema, **kwargs):
        if not self.structured:
            raise NotImplementedError
        return RunnableLambda(lambda _: STRUCTURED[schema])

    def _tool_args(self) -> dict:
        start = (pd.Timestamp(self.trade_date) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        return {
            "symbol": self.ticker, "ticker": self.ticker,
            "curr_date": self.trade_date, "start_date": start, "end_date": self.trade_date,
            "indicator": "rsi", "topic": "Fed rate cut", "freq": "quarterly",
        }

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(1)
        usage = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        if self.tools and not isinstance(messages[-1], ToolMessage):
            args = self._tool_args()
            calls = []
            for i, t in enumerate(self.tools):
                props = t.tool_call_schema.model_json_schema()["properties"]
                calls.append({"name": t.name, "id": f"call_{i}",
                              "args": {k: v for k, v in args.items() if k in props}})
            self.last_tool_args = [c["args"] for c in calls]
            message = AIMessage(content="", tool_calls=calls, usage_metadata=usage)
        else:
            message = AIMessage(content=TEXT, usage_metadata=usage)
        return ChatResult(generations=[ChatGeneration(message=message)])


class _Client:
    def __init__(self, model):
        self.model = model

    def get_llm(self):
        return self.model


class ScriptedLLMSource:
    """Patches ``create_tier_client`` so deep and quick get the same ScriptedModel."""

    id = "scripted-llm-v1"

    def __init__(self, ticker: str = "NVDA", trade_date: str = "2026-01-09",
                 structured: bool = False):
        self.ticker = ticker
        self.trade_date = trade_date
        self.structured = structured
        self._model = ScriptedModel(
            structured=structured, ticker=ticker, trade_date=trade_date)

    def chat_model(self, tier: str) -> BaseChatModel:
        return self._model

    def snapshot_id(self) -> str:
        suffix = "-structured" if self.structured else ""
        return f"scripted-llm-v1:{self.ticker}:{self.trade_date}{suffix}"

    @contextmanager
    def activate(self) -> Iterator[None]:
        from tradingagents.graph import trading_graph

        saved = trading_graph.create_tier_client
        model = self._model
        # Start every run with an empty call history: a reused source must not
        # carry one run's calls into the next (a "fail on call N" stub would
        # otherwise fire in a later run).
        model.calls.clear()
        try:
            trading_graph.create_tier_client = (
                lambda config, tier, **k: _Client(model))
            yield
        finally:
            trading_graph.create_tier_client = saved


class EvalContext:
    """Combines a data source and an LLM source; both patches live only inside."""

    def __init__(self, source: Source, llm: LLMSource):
        self.source = source
        self.llm = llm

    @contextmanager
    def activate(self) -> Iterator[None]:
        with ExitStack() as stack:
            stack.enter_context(self.source.activate())
            stack.enter_context(self.llm.activate())
            yield
