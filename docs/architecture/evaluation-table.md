# Candidate Evaluation Table (D2.8)

The comparison that justifies the chosen architecture. Scoped to the NFR-E1
evaluation harness; other feature branches keep their own comparisons.

Candidates (see ADR-001):
- A: standalone runner, no graph contact
- B: fake vendors only, real LLM
- C: full recording/replay now (FR-E4)
- D: scripted source + real graph, protocol-shaped for replay (**selected**)

| Criterion | A | B | C | D (chosen) |
|---|---|---|---|---|
| Tests the real shipped graph | ✗ | ✓ | ✓ | ✓ |
| Deterministic | ✓ | ✗ (LLM) | ✓ | ✓ |
| Offline / no network | ✓ | ✗ | ✓ (after capture) | ✓ |
| Cost | low | high | medium | low |
| Time to first result | low | high | high (needs capture) | low |
| Proves real-input reproducibility | ✗ | ✗ | ✓ | ✗ (deferred, FR-E4) |
| Production code unchanged | ✓ | ✓ | ✓ | ✓ |
| Replay-ready for FR-E4 | ✗ | ✗ | (it is replay) | ✓ (protocols) |

**Decision:** D. It is the only option that tests the real graph, is
deterministic, runs offline, and leaves a clean path to recorded replay without
changing production code. C is the upgrade path when FR-E4 is approved.

**Trade-offs accepted:** D does not prove real-input reproducibility; the
scripted source must track production patch points.
