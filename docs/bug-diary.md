# Bug Diary (D4)

One entry per significant bug: symptom, reproduction, classification, root cause,
fix, and which invariant gap it exposed.

> Template below. Entries are added as real bugs are found; nothing here is
> invented.

---

## Template

### BUG-`<n>`: `<title>`

- Date: TODO
- Symptom: TODO
- Reproduction: TODO
- Classification: TODO (e.g. logic / data / structured-output / eval / gate)
- Root cause: TODO
- Fix: TODO (commit/PR)
- Invariant gap exposed: TODO (which entry in `docs/architecture/invariants.md`)

---

## Recorded bugs

### BUG-001: `tool_calls_total` double-counted tool calls

- Symptom: the eval manifest's `tool_calls_total` was 24 when only 12 tools
  executed.
- Reproduction: run one golden case; compare `tool_calls_total` to
  `tokens.tool_calls`.
- Classification: eval / accounting.
- Root cause: `tool_events` collected both the AIMessage "requested" records and
  the ToolMessage "ok" records for the same call, and the total counted all
  events.
- Fix: `tool_calls_total` counts only `status == "ok"`; added
  `tool_call_requests_total` for requests; `test_manifest_tool_counts_from_stream`
  asserts the equality with `tokens.tool_calls`.
- Invariant gap exposed: accounting consistency (related to FR-E2 manifest
  completeness) — the manifest must reflect actual execution, not requested
  calls.
