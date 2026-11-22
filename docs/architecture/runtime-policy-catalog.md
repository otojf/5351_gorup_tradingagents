# Runtime Policy Catalog (D2.7)

What the system does when each degraded or failure path is triggered. Behavioral
rules for runtime, so failures are visible and bounded rather than silent.

| Path | Trigger | Behavior | Visible via |
|---|---|---|---|
| Structured-output fallback | Provider does not support `with_structured_output` (e.g. scripted source) | Falls back to free-text generation; logs a notice per agent | Log lines "falling back to free-text generation"; `degradations` (baseline logs only — see manifest note) |
| Structured parse failure (owner D) | Structured output unparseable / schema-invalid | Retry once, then mark DEGRADED and continue (no silent drop) | DEGRADED marker + `degradation_count` (owner D) |
| Unparseable final rating | Portfolio Manager output has no parseable rating | `run_rating` returns `REVIEW` sentinel, not a fabricated rating | `final_rating == "REVIEW"` |
| Vendor data missing / no key (owner C) | Data source unconfigured or missing credentials | Skip the source and record it; do not retry within the run | skip log; `vendor_skip_count` (owner C) |
| Vendor error | Vendor call raises | Routed error handling; run continues with available data | Vendor error logs |
| Memory settlement failure | Settling past decisions fails | Run continues; `memory_note` records what could not be settled | `memory_note` in state/report |
| Memory read failure | Reading the log fails | Run continues with empty past context; note recorded | `memory_note` |
| Checkpoint mismatch | Resume under changed settings/analysts | Start fresh (signature change) instead of resuming stale state | log "Starting fresh" |
| Eval manifest unavailable field | degradations / risk / traceability not in baseline | Record `null` with a reason in `unavailable_sources`; never fake | `manifest.json` |
| Eval run isolation | Two runs of the same case | Each run gets its own `run_id` and dirs; no cross-run feed | distinct `run_id` / paths |
| CI gate failure | Any of the six gates fails | Merge blocked; bad PR reported | Actions checks; branch protection |
| Test-approval missing | Approval record TODO | Gate 1 fails by design | gate-1 check red |

## Principles

1. **No silent degradation.** A degraded path is always marked.
2. **Bounded failure.** A failure is recorded and the run continues where safe;
   it does not fabricate a result.
3. **Authority.** Deterministic code decides safety-relevant outcomes; model
   output is advisory.
