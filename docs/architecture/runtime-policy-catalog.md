# Runtime Policy Catalog (D2.7)

What the system does when each degraded or failure path is triggered. Behavioral
rules for runtime, so failures are visible and bounded rather than silent.

| Path | Trigger | Behavior | Visible via |
|---|---|---|---|
| Structured-output fallback | Provider does not support `with_structured_output` (e.g. scripted source) | Falls back to free-text generation; logs a notice per agent | Log lines "falling back to free-text generation"; degradation event |
| Structured parse failure | Structured output unparseable / schema-invalid | Initial attempt plus up to two retries (`MAX_ATTEMPTS=3`); failed attempts before the last are `RETRY`; after the last failure mark `DEGRADED` and continue with free text | DEGRADED marker + `degradation_count`; report section warning |
| Risk gate: missing or invalid portfolio | No portfolio snapshot, malformed snapshot, or unusable target position | Fail closed: `NEEDS_REVIEW` from the gate; public `final_rating` becomes `REVIEW`; the run continues and the report is still written | `risk_verdict` / `final_rating`; audit record |
| Risk gate: audit write failure | Audit destination unavailable or unwritable | No actionable signal is published; public rating is `REVIEW`; the error is logged/raised to the caller | `REVIEW` in CLI/API; audit error |
| Unparseable final rating | Portfolio Manager output has no parseable rating | `run_rating` returns `REVIEW` sentinel, not a fabricated rating | `final_rating == "REVIEW"` |
| FRED missing or blank key | FRED_API_KEY absent/blank | Skip FRED once for the current run, record one skip, do not send HTTP, continue to a configured fallback | Skip log; `vendor_skip_count` |
| FRED waiter timeout | A concurrent caller waits for the first check and times out | Do not enter the vendor source; take the vendor fallback path; do not record a skip for the timeout | Timeout diagnostic + fallback log |
| Vendor error | Vendor call raises | Routed error handling; run continues with available data | Vendor error logs |
| Memory settlement failure | Settling past decisions fails | Run continues; `memory_note` records what could not be settled | `memory_note` in state/report |
| Memory read failure | Reading the log fails | Run continues with empty past context; note recorded | `memory_note` |
| Checkpoint mismatch | Resume under changed settings/analysts | Start fresh (signature change) instead of resuming stale state | log "Starting fresh" |
| Eval manifest unavailable field | A producer for `degradations` / `risk_verdicts` / `traceability` is absent | Record `null` with a reason in `unavailable_sources`; never fake | `manifest.json` |
| Eval run isolation | Two runs of the same case | Each run gets its own `run_id` and dirs; no cross-run feed | distinct `run_id` / paths |
| CI gate failure | Any of the six gates fails | Merge blocked; bad PR reported | Actions checks; branch protection |
| Test-approval missing | Approval record TODO | Gate 1 fails until the record is complete | gate-1 check red |

## Principles

1. **No silent degradation.** A degraded path is always marked.
2. **Bounded failure.** A failure is recorded and the run continues where safe;
   it does not fabricate a result.
3. **Authority.** Deterministic code decides safety-relevant outcomes;
   model output is advisory.
