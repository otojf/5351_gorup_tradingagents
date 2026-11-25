"""Shared helpers for invoking an agent with structured output and a graceful fallback.

The Portfolio Manager, Trader, Research Manager and Sentiment Analyst all follow
the same canonical pattern:

1. At agent creation, wrap the LLM with ``with_structured_output(Schema)``
   so the model returns a typed Pydantic instance. If the provider does
   not support structured output (rare; mostly older Ollama models), the
   wrap is skipped and the agent uses free-text generation instead.
2. At invocation, run the structured call and render the result back to
   markdown. A call that yields no parsed result or fails validation is
   retried twice (three attempts at most). A failure before the last attempt
   is the ``retry`` middle state and is only logged. If every attempt fails,
   the agent falls back to a plain ``llm.invoke`` so the pipeline never
   blocks, and the failure is reported as a DEGRADED event (FR-D2 / INV-D1)
   that the report names on the degraded section. A fallback is never silent.

Centralising the pattern here keeps the agent factories small and ensures
all four agents report degradation the same way.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# The marker a structured failure is reported under. Kept as a plain constant
# (not an enum) so it survives being written into a report or a manifest.
DEGRADED = "DEGRADED"

# The middle state of a failed attempt that will be retried. It is logged but
# never reaches the report: only a run that exhausts every attempt degraded.
RETRY = "retry"

# Our own status value for a successful structured call.
OK = "ok"

# Why a structured call degraded. ``NO_PARSE`` covers both "the model answered
# in plain text instead of calling the tool" and "the result failed schema
# validation"; from the caller's side they are the same miss. Providers that
# cannot bind a schema at all are not retried and report the other reason.
NO_PARSE = "no_parse"
PROVIDER_UNSUPPORTED = "provider_unsupported"

# The structured call is attempted once, then retried twice: three calls at
# most. Two retries give a transient provider hiccup room to clear while still
# bounding the cost of a model that simply cannot produce the schema.
MAX_ATTEMPTS = 3

# Schema-only structured output binds exactly one tool (the schema itself), so a
# model that reaches for a search tool emits an unknown tool call and the whole
# structured attempt is discarded for a free-text retry. Agents on this path
# state the constraint explicitly rather than relying on the binding alone
# (#1130).
NO_EXTERNAL_TOOLS = (
    "Use only the evidence provided in this prompt. Do not call external tools "
    "or search the web; if something is missing, say so explicitly."
)


@dataclass(frozen=True)
class StructuredOutcome:
    """What a structured call produced, and whether it had to degrade.

    ``value`` is the typed result when ``status`` is ``OK``. ``attempts`` is the
    number of calls made (0 when the provider could not bind a schema);
    ``retry_count`` is how many of those attempts failed before the call
    succeeded or the budget ran out.
    """

    value: Any | None
    status: str
    reason: str | None = None
    attempts: int = 0
    retry_count: int = 0

    @property
    def degraded(self) -> bool:
        """Whether this outcome exhausted every attempt and fell back."""
        return self.status == DEGRADED

    @property
    def marker(self) -> str | None:
        """The report marker for this outcome, or ``None`` when it succeeded."""
        return DEGRADED if self.degraded else None

    def as_event(self, agent_name: str, section: str = "") -> dict:
        """The record an agent adds to ``structured_degradations`` for this outcome.

        ``section`` is the report path the agent writes to, so the report can
        warn on that section rather than the whole document.
        """
        return {
            "agent": agent_name,
            "section": section,
            "reason": self.reason,
            "attempts": self.attempts,
            "retry_count": self.retry_count,
            "marker": self.marker,
        }


def bind_structured(llm: Any, schema: type[T], agent_name: str) -> Any | None:
    """Return ``llm.with_structured_output(schema)`` or ``None`` if unsupported.

    Logs a warning when the binding fails so the user understands the agent
    will use free-text generation for every call instead of one-shot fallback.
    """
    try:
        return llm.with_structured_output(schema)
    except (NotImplementedError, AttributeError) as exc:
        logger.warning(
            "%s: provider does not support with_structured_output (%s); "
            "falling back to free-text generation",
            agent_name, exc,
        )
        return None


def invoke_structured(
    structured_llm: Any | None, prompt: Any, agent_name: str
) -> StructuredOutcome:
    """Run the structured call, retrying twice, and report any degradation.

    ``prompt`` is whatever the underlying LLM accepts (a string for chat
    invocations, a list of message dicts for chat models that take that
    shape), so a caller can forward the same value to its free-text fallback.
    """
    if structured_llm is None:
        logger.warning(
            "%s: no structured-output binding available; DEGRADED", agent_name
        )
        return StructuredOutcome(
            value=None, status=DEGRADED, reason=PROVIDER_UNSUPPORTED, attempts=0
        )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = structured_llm.invoke(prompt)
            if result is None:
                # A thinking model can answer in plain text instead of calling
                # the tool, leaving the parser with nothing to return. Treat it
                # as a structured miss and retry, with a clear reason.
                raise ValueError("structured output returned no parsed result")
            return StructuredOutcome(
                value=result, status=OK, attempts=attempt,
                retry_count=attempt - 1,
            )
        except Exception as exc:  # noqa: BLE001 - any failure means retry
            status = RETRY if attempt < MAX_ATTEMPTS else DEGRADED
            logger.warning(
                "%s: structured-output attempt %d/%d failed (%s); %s",
                agent_name, attempt, MAX_ATTEMPTS, exc,
                "retrying" if status == RETRY else "DEGRADED",
            )

    return StructuredOutcome(
        value=None, status=DEGRADED, reason=NO_PARSE,
        attempts=MAX_ATTEMPTS, retry_count=MAX_ATTEMPTS - 1,
    )


def invoke_structured_or_freetext(
    structured_llm: Any | None,
    plain_llm: Any,
    prompt: Any,
    render: Callable[[T], str],
    agent_name: str,
    on_degraded: Callable[[StructuredOutcome], None] | None = None,
) -> str:
    """Run the structured call and render to markdown; fall back to free-text on any failure.

    ``on_degraded`` receives the outcome whenever the structured path degraded,
    so the caller can record the event. The fallback is never silent.
    """
    outcome = invoke_structured(structured_llm, prompt, agent_name)
    if outcome.degraded:
        if on_degraded is not None:
            on_degraded(outcome)
        return plain_llm.invoke(prompt).content
    if outcome.value is None:
        raise RuntimeError("structured outcome marked OK without a value")
    return render(outcome.value)
