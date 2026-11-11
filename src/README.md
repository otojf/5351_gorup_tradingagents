# src/ — Mapping Only (No Physical Migration)

The course's §5/D8 structure names `src/` for the full application source. This
repository keeps its baseline layout and does **not** physically move source into
`src/`. This file is the required mapping so reviewers can locate the source.

| Spec path | Actual path | Contents |
|---|---|---|
| `src/` | `tradingagents/` | Core framework: agents (analysts/researchers/managers/trader/risk_mgmt), graph, dataflows, llm_clients, memory, state. |
| `src/` | `cli/` | CLI entry (`cli.main:app`), display, prefs, selections, stats handler. |

Why no physical migration: the baseline is an upstream-derived package named
`tradingagents`; moving it under `src/` would break the package name, every
import, and the `tradingagents` console entry point. The `integration` marker
already separates live tests (see `test/`). A physical migration remains a
team/PM decision.

Full mapping: `docs/architecture/repository-structure-mapping.md`.
