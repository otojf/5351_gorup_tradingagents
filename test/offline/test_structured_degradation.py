"""FR-D2 / INV-D1: structured output retries twice, then marks DEGRADED.

A structured parse that yields no result, or fails schema validation, is
retried exactly twice (three attempts at most). Each failed attempt before the
last is a ``retry`` middle state: it is logged but never reaches the report.
If every attempt fails the run continues on free text, and the failure is
recorded as a DEGRADED event in the graph state, in the report header and on
the degraded section itself. Nothing is dropped silently.
"""

from unittest.mock import MagicMock

import pytest

from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.schemas import (
    PortfolioDecision,
    PortfolioRating,
    ResearchPlan,
    render_research_plan,
)
from tradingagents.agents.structured import (
    DEGRADED,
    MAX_ATTEMPTS,
    NO_PARSE,
    PROVIDER_UNSUPPORTED,
    RETRY,
    StructuredOutcome,
    invoke_structured,
    invoke_structured_or_freetext,
)
from tradingagents.agents.trader.trader import create_trader
from tradingagents.reporting import write_report_tree

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan() -> ResearchPlan:
    return ResearchPlan(
        recommendation=PortfolioRating.BUY,
        rationale="Bull case stronger on demand.",
        strategic_actions="Add in tranches.",
    )


def _decision() -> PortfolioDecision:
    return PortfolioDecision(
        rating=PortfolioRating.HOLD,
        executive_summary="Sit tight.",
        investment_thesis="Evidence balanced.",
    )


def _structured_sequence(*results):
    """A structured LLM whose invoke returns or raises the given items, in order."""
    structured = MagicMock()
    state = {"n": 0}

    def _invoke(_prompt):
        index = min(state["n"], len(results) - 1)
        state["n"] += 1
        item = results[index]
        if isinstance(item, Exception):
            raise item
        return item

    structured.invoke.side_effect = _invoke
    structured.call_count = 0
    return structured


def _plain_llm(text: str = "FREE TEXT") -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=text)
    return llm


def _rm_state():
    return {
        "company_of_interest": "NVDA",
        "investment_debate_state": {
            "history": "Bull and bear here.",
            "bull_history": "",
            "bear_history": "",
            "current_response": "",
            "count": 1,
        },
    }


def _trader_state():
    return {
        "company_of_interest": "NVDA",
        "investment_plan": "**Recommendation**: Buy",
        "market_report": "",
    }


def _pm_state():
    return {
        "company_of_interest": "NVDA",
        "past_context": "",
        "risk_debate_state": {
            "history": "Risk debate.",
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "count": 1,
        },
        "investment_plan": "**Recommendation**: Buy",
        "trader_investment_plan": "**Action**: Buy",
    }


# ---------------------------------------------------------------------------
# Retry / degrade state machine
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_max_attempts_is_three():
    # Two retries on top of the first attempt: three calls at most.
    assert MAX_ATTEMPTS == 3


@pytest.mark.unit
def test_success_on_first_attempt_does_not_retry():
    structured = _structured_sequence(_plan())
    outcome = invoke_structured(structured, "p", "Research Manager")

    assert structured.invoke.call_count == 1
    assert outcome.status == "ok"
    assert outcome.attempts == 1
    assert outcome.retry_count == 0
    assert outcome.degraded is False


@pytest.mark.unit
def test_success_on_second_attempt_counts_one_retry():
    structured = _structured_sequence(ValueError("bad"), _plan())
    outcome = invoke_structured(structured, "p", "Research Manager")

    assert structured.invoke.call_count == 2
    assert outcome.status == "ok"
    assert outcome.retry_count == 1


@pytest.mark.unit
def test_success_on_third_attempt_counts_two_retries():
    structured = _structured_sequence(ValueError("bad"), ValueError("bad"), _plan())
    outcome = invoke_structured(structured, "p", "Research Manager")

    assert structured.invoke.call_count == 3
    assert outcome.status == "ok"
    assert outcome.retry_count == 2
    assert outcome.degraded is False


@pytest.mark.unit
def test_three_failures_degrade():
    structured = _structured_sequence(ValueError("a"), ValueError("b"), ValueError("c"))
    outcome = invoke_structured(structured, "p", "Research Manager")

    assert structured.invoke.call_count == 3
    assert outcome.status == DEGRADED
    assert outcome.degraded is True
    assert outcome.reason == NO_PARSE
    assert outcome.attempts == 3
    assert outcome.retry_count == 2
    assert outcome.marker == DEGRADED


@pytest.mark.unit
def test_exactly_three_attempts_bounds_the_cost():
    # A model that never answers must not be called more than the retry budget.
    structured = _structured_sequence(ValueError("always"))
    invoke_structured(structured, "p", "Research Manager")
    assert structured.invoke.call_count == MAX_ATTEMPTS


@pytest.mark.unit
def test_no_parsed_result_is_retried_then_degraded():
    # A thinking model can return None instead of calling the tool: a miss.
    structured = _structured_sequence(None, None, None)
    outcome = invoke_structured(structured, "p", "Research Manager")

    assert structured.invoke.call_count == 3
    assert outcome.status == DEGRADED
    assert outcome.reason == NO_PARSE


@pytest.mark.unit
def test_unbound_provider_degrades_without_attempts():
    outcome = invoke_structured(None, "p", "Research Manager")

    assert outcome.status == DEGRADED
    assert outcome.reason == PROVIDER_UNSUPPORTED
    assert outcome.attempts == 0
    assert outcome.retry_count == 0


@pytest.mark.unit
def test_retry_is_a_middle_state_not_a_report_marker():
    assert RETRY != DEGRADED
    outcome = StructuredOutcome(value=None, status=RETRY, reason=NO_PARSE,
                                attempts=1, retry_count=1)
    assert outcome.degraded is False
    assert outcome.marker is None


@pytest.mark.unit
def test_outcome_as_event_names_agent_and_section():
    outcome = StructuredOutcome(value=None, status=DEGRADED, reason=NO_PARSE,
                                attempts=3, retry_count=2)
    event = outcome.as_event("Trader", "3_trading/trader.md")

    assert event["agent"] == "Trader"
    assert event["section"] == "3_trading/trader.md"
    assert event["reason"] == NO_PARSE
    assert event["attempts"] == 3
    assert event["retry_count"] == 2
    assert event["marker"] == DEGRADED


# ---------------------------------------------------------------------------
# Free-text wrapper: the fallback is never silent
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_freetext_fallback_returns_text_and_reports_degradation():
    structured = _structured_sequence(ValueError("always"))
    reported = []
    out = invoke_structured_or_freetext(
        structured, _plain_llm("FREE"), "p", render_research_plan, "Research Manager",
        on_degraded=reported.append,
    )

    assert out == "FREE"
    assert len(reported) == 1
    assert reported[0].status == DEGRADED


@pytest.mark.unit
def test_structured_success_does_not_report_degradation():
    structured = _structured_sequence(_plan())
    reported = []
    out = invoke_structured_or_freetext(
        structured, _plain_llm("FREE"), "p", render_research_plan, "Research Manager",
        on_degraded=reported.append,
    )

    assert "**Recommendation**: Buy" in out
    assert reported == []


@pytest.mark.unit
def test_retry_middle_state_does_not_report_degradation():
    # A run that succeeds on the second attempt is not a degraded run.
    structured = _structured_sequence(ValueError("bad"), _plan())
    reported = []
    invoke_structured_or_freetext(
        structured, _plain_llm("FREE"), "p", render_research_plan, "Research Manager",
        on_degraded=reported.append,
    )
    assert reported == []


# ---------------------------------------------------------------------------
# Each agent records its own fallback in state
# ---------------------------------------------------------------------------


def _degraded_structured_llm():
    structured = _structured_sequence(ValueError("always"))
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    llm.invoke.return_value = MagicMock(content="FREE TEXT")
    return llm


@pytest.mark.unit
def test_research_manager_emits_degraded_event():
    result = create_research_manager(_degraded_structured_llm())(_rm_state())
    events = result["structured_degradations"]
    assert len(events) == 1
    assert events[0]["agent"] == "Research Manager"
    assert events[0]["marker"] == DEGRADED


@pytest.mark.unit
def test_trader_emits_degraded_event():
    result = create_trader(_degraded_structured_llm())(_trader_state())
    events = result["structured_degradations"]
    assert len(events) == 1
    assert events[0]["agent"] == "Trader"
    assert events[0]["marker"] == DEGRADED


@pytest.mark.unit
def test_portfolio_manager_emits_degraded_event():
    result = create_portfolio_manager(_degraded_structured_llm())(_pm_state())
    events = result["structured_degradations"]
    assert len(events) == 1
    assert events[0]["agent"] == "Portfolio Manager"
    assert events[0]["marker"] == DEGRADED


@pytest.mark.unit
def test_successful_agents_emit_no_event():
    structured = _structured_sequence(_plan())
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    llm.invoke.return_value = MagicMock(content="FREE TEXT")
    result = create_research_manager(llm)(_rm_state())
    assert result["structured_degradations"] == []


@pytest.mark.unit
def test_invariant_no_silent_degradation():
    # INV-D1: 20 forced failures -> 20 visible events, 0 silent.
    events = 0
    for _ in range(20):
        outcome = invoke_structured(
            _structured_sequence(ValueError("x")), "p", "Research Manager"
        )
        if outcome.degraded:
            events += 1
    assert events == 20


# ---------------------------------------------------------------------------
# The report says the run degraded, and says which section did
# ---------------------------------------------------------------------------


def _base_state() -> dict:
    return {
        "trade_date": "2026-01-15",
        "market_report": "MKT",
        "investment_debate_state": {"bull_history": "BULL"},
        "investment_plan": "RM PLAN",
        "trader_investment_plan": "TRADE",
        "risk_debate_state": {"neutral_history": "NEUTRAL"},
        "final_trade_decision": "**Rating**: Hold",
        "structured_degradations": [
            {
                "agent": "Trader",
                "section": "3_trading/trader.md",
                "reason": NO_PARSE,
                "attempts": 3,
                "retry_count": 2,
                "marker": DEGRADED,
            }
        ],
    }


@pytest.mark.unit
def test_degraded_marker(tmp_path):
    complete = write_report_tree(_base_state(), "NVDA", tmp_path).read_text(encoding="utf-8")
    header = complete.split("## ")[0]
    assert "DEGRADED" in header


@pytest.mark.unit
def test_degraded_section_warning_in_markdown(tmp_path):
    write_report_tree(_base_state(), "NVDA", tmp_path)
    section = (tmp_path / "3_trading" / "trader.md").read_text(encoding="utf-8")
    assert "DEGRADED" in section
    assert "no_parse" in section
    assert section.endswith("TRADE")


@pytest.mark.unit
def test_degraded_section_warning_in_html(tmp_path):
    write_report_tree(_base_state(), "NVDA", tmp_path)
    page = (tmp_path / "complete_report.html").read_text(encoding="utf-8")
    assert "DEGRADED" in page
    assert "degraded-warning" in page


@pytest.mark.unit
def test_non_degraded_section_has_no_warning(tmp_path):
    write_report_tree(_base_state(), "NVDA", tmp_path)
    market = (tmp_path / "1_analysts" / "market.md").read_text(encoding="utf-8")
    assert "DEGRADED" not in market


@pytest.mark.unit
def test_report_without_degradation_has_no_warning(tmp_path):
    state = _base_state()
    state["structured_degradations"] = []
    complete = write_report_tree(state, "NVDA", tmp_path).read_text(encoding="utf-8")
    assert "DEGRADED" not in complete
