"""Offline, reproducible eval harness (Slice 1).

Proves the harness and graph structure are deterministic under fixed scripted
data and a scripted model. Real-input reproducibility needs recorded replay.
"""

from .compare import compare
from .golden import GOLDEN_SET, GoldenCase
from .runner import CaseResult, run_case, run_suite
from .sources import EvalContext, ScriptedLLMSource, ScriptedSource

__all__ = [
    "GOLDEN_SET",
    "GoldenCase",
    "CaseResult",
    "run_case",
    "run_suite",
    "compare",
    "EvalContext",
    "ScriptedLLMSource",
    "ScriptedSource",
]
