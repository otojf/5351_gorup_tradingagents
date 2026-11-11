# Option Ledger (D2.11, optional)

Rejected architectural options and when they should be reconsidered. Complements
the ADRs (the chosen path and its rationale live in `adr/`).

| Option | Rejected because | Reconsider when |
|---|---|---|
| Standalone evaluation runner that mimics the pipeline (no graph contact) | Would test a replica, not the shipped graph; determinism would say nothing about production. | Never for the shipped claim; only for a pure unit harness. |
| Fake vendors only, real LLM in eval | LLM output is non-deterministic and networked; ratings cannot be stable or run offline. | Never for the offline claim. |
| Full recording/replay now (FR-E4) | Heavier; needs an initial network capture per case; separate requirement. | FR-E4 is approved; the `Source`/`LLMSource` protocols already allow a drop-in recording source. |
| Physical `src/` + `test/offline|live/` migration | Renaming the import root would break packaging and every import; the `integration` marker already separates live tests. | Team/PM decides the spec-structural benefit outweighs churn. |
| Separate risk-gate graph node as the safety guarantee (owner A) | A separate node is not itself a guarantee; correctness must not depend on graph topology. | See owner A's ADR; not reconsidered here. |
| Lifting FR-E1/E2/E3/INV-E1 to top-level registry entries now | Kept nested under NFR-E1 pending team/instructor confirmation. | Team/instructor confirms top-level entries are wanted. |
| `include`-merge to add a 5th matrix check in CI gate-5 | `strategy.matrix.include` merges into an existing combination; it does not add one. | A genuinely new check is wanted; add an explicit matrix entry instead. |
