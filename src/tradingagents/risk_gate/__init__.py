"""FR-A1 deterministic risk gate: a pure, offline, auditable risk engine.

Public API:
- ``RiskInputs`` and its parts (structured inputs)
- ``RiskPolicy`` (versioned, with a stable ``policy_hash``)
- ``evaluate_risk`` (pure evaluation)
- ``RiskEvaluation``, ``RiskAuditRecord``, and the enums (structured outputs)

The core has no network, file I/O, LLM, or LangGraph dependency. Integration
(graph/CLI wiring, audit persistence) is a separate stage.
"""

from __future__ import annotations

from .engine import audit_id_for, evaluate_risk
from .models import (
    DecisionStatus,
    Holding,
    PortfolioRiskSnapshot,
    RiskAuditRecord,
    RiskEvaluation,
    RiskInputs,
    RiskVerdict,
    RuleOutcome,
    RuleResult,
    TargetPosition,
)
from .policy import DEFAULT_POLICY, DEFAULT_VERSION, RiskPolicy

__all__ = [
    "DEFAULT_POLICY",
    "DEFAULT_VERSION",
    "DecisionStatus",
    "Holding",
    "PortfolioRiskSnapshot",
    "RiskAuditRecord",
    "RiskEvaluation",
    "RiskInputs",
    "RiskPolicy",
    "RiskVerdict",
    "RuleOutcome",
    "RuleResult",
    "TargetPosition",
    "audit_id_for",
    "evaluate_risk",
]
