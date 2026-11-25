# Structural Constraints (D3)

Module organization rules the coding agent must follow. These constrain *how* code
is laid out, not just *what* it does.

## 1. One architectural element, one module

Each architectural element maps to exactly one module. Do not duplicate an
element across modules.

| Element | Module |
|---|---|
| The four analysts | `src/tradingagents/agents/analysts/` |
| Bull/Bear researchers | `src/tradingagents/agents/researchers/` |
| Research Manager, Portfolio Manager | `src/tradingagents/agents/managers/` |
| Trader | `src/tradingagents/agents/trader/` |
| Risk debate analysts | `src/tradingagents/agents/risk_mgmt/` |
| Graph orchestration | `src/tradingagents/graph/` |
| Vendor routing / adapters | `src/tradingagents/dataflows/` |
| Provider clients | `src/tradingagents/llm_clients/` |
| Memory | `src/tradingagents/memory/` |
| Risk gate | `src/tradingagents/risk_gate/` |
| Citation checker | `src/fr_b2/` |
| CLI | `src/cli/` |
| Evaluation harness | `src/eval/` |
| CI gates | `scripts/ci/` |

## 2. Extend, never replace

New work **extends** the existing baseline (`src/tradingagents/`, `src/cli/`,
`test/`, `src/eval/`). Never replace or rewrite a baseline module wholesale. Additive changes
(new keys, new functions, new files) are preferred; a breaking change to an
existing contract requires an ADR.

## 3. Every module and function references its decision and invariant

A new file states in its module docstring which ADR and invariant it implements:

```python
"""Implements ADR-001 (eval harness) and INV-E1 (no merge with failing gate)."""
```

A function that enforces safety behavior names the requirement/invariant it
serves. Tests reference the requirement/invariant they verify (see
`verification-constraints.md`).

## 4. Authority boundaries (structural)

Deterministic decisions do not live inside LLM nodes. Specifically:

- Rating normalization: `src/tradingagents/agents/rating.py`, not inside a manager.
- Tool-call counting: `src/cli/stats_handler.py`, not estimated by a model.
- Risk gate: `src/tradingagents/risk_gate/`; citation checker: `src/fr_b2/`.
  The token budget is not implemented (NFR-C1 is partial), so there is no budget
  module to point at.

## 5. Layering

- `src/tradingagents/dataflows/` and `src/tradingagents/llm_clients/` are the
  only places that reach the network.
- `src/tradingagents/agents/*` call the vendor router and LLM client factories;
  they do not import vendor modules directly or instantiate provider clients inline.
- `src/eval/` patches only through the `Source`/`LLMSource` protocols and must
  not change production behavior.
- `src/fr_b2/` is an offline CLI/checker and never calls a model.
- `scripts/ci/` may read any file; it must not import or mutate application state.

## 6. State contract

State keys are declared in `src/tradingagents/agents/state.py` (`AgentState`).
Adding a key is additive. Never repurpose an existing key. New keys are added by
the owning feature branch with an ADR reference.

## 7. Enforcement

- `ruff check .` (gate 2) catches import order and basic structural issues.
- `pytest` (gate 5) includes layering tests (e.g. `test/offline/test_layering.py`).
- Structural review happens in `docs/review-memo.md` per PR.
