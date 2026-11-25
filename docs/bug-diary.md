# Bug Diary (D4)

One entry per significant bug: symptom, reproduction, classification, root
cause, fix, and which invariant gap it exposed.

## BUG-001: `tool_calls_total` double-counted tool calls

- Date: 2026-11-11
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
- Invariant gap exposed: accounting consistency (FR-E2 manifest completeness) —
  the manifest must reflect actual execution, not requested calls.

## BUG-002: FRED counters conflated requests, source entries, HTTP and logs

- Date: 2026-11-18
- Symptom: the first FR-C2 tests could not tell whether a repeated request had
  stopped at the tool, the vendor source, the HTTP layer, or the log.
- Reproduction: send several macro-indicator requests in one run with no FRED
  key and compare the four counters.
- Classification: data / test instrumentation.
- Root cause: the test counters measured one blended "call" instead of the four
  distinct boundaries.
- Fix: separate counters for tool requests, data-source entries, HTTP attempts
  and skip logs; `test_missing_key_one_log_no_http_sentinel_per_call` and the
  concurrency/isolation tests assert each boundary (`0e948f2`).
- Invariant gap exposed: NFR-C1/FR-C2 evidence must measure the boundary the
  requirement names; a blended counter can hide a retry.

## BUG-003: risk-gate integration changed downstream expected ratings

- Date: 2026-11-20
- Symptom: eval and FRED tests expected `Overweight`, but the integrated run
  published `REVIEW` because no portfolio snapshot was supplied.
- Reproduction: run the fixed golden cases through the integrated graph.
- Classification: integration / cross-feature contract.
- Root cause: a fixed rating assertion belonged to another feature's output
  boundary; the new gate could legitimately change the effective rating.
- Fix: the eval/FRED tests now accept `REVIEW` where the gate lacks a portfolio
  snapshot, while retaining their own repeatability and vendor-skip assertions
  (`17be598`, `4d2c80a`, `71eba39`).
- Invariant gap exposed: cross-feature test ownership — each test must assert
  the value its own requirement owns, and the report should explain the
  precedence.

## BUG-004: approved HOLD downgraded and malformed portfolio crashed

- Date: 2026-11-20
- Symptom: an approved HOLD became `REVIEW`; `position_sizing` was ignored;
  production callers did not supply `risk_portfolio`; malformed input could
  crash instead of failing closed.
- Reproduction: the FR-A1 adapter tests with an approved HOLD, a sizing string,
  a CLI run without a snapshot, and a non-mapping portfolio.
- Classification: logic / safety boundary.
- Root cause: the adapter treated every non-BUY as `REVIEW`, did not parse
  sizing, lacked a production portfolio injection path, and did not catch
  snapshot errors.
- Fix: approved HOLD keeps the model rating; position sizing is parsed and can
  only tighten/reject; `--risk-portfolio` injects the snapshot; malformed
  input returns `NEEDS_REVIEW`/`PENDING_REVIEW` (`b2d240b`).
- Invariant gap exposed: INV-A1 — fail closed without turning a safe, approved
  HOLD into a false review.

## BUG-005: citation checker output could overwrite registered evidence

- Date: 2026-11-19
- Symptom: `--out` pointed at an evidence file registered in the source table
  could overwrite the evidence used to verify the citation.
- Reproduction: copy the evidence, point `--out` at it, and compare bytes.
- Classification: security / evidence integrity.
- Root cause: input-path protection covered direct inputs but not every
  registered evidence path.
- Fix: refuse output collisions with registered evidence; add a regression test
  expecting exit code 2 and unchanged bytes (`04ad26f`, `8638e57`).
- Invariant gap exposed: INV-B1 — a checker must not destroy the evidence it is
  checking.

## BUG-006: manifest `prompt_snapshot` was a label, not a hash

- Date: 2026-11-19
- Symptom: the manifest field named `prompt_snapshot` looked like a content hash
  but was a static label.
- Reproduction: change one prompt module's bytes in a copied tree and compare the
  manifest field.
- Classification: evaluation / provenance.
- Root cause: the label was recorded as if it were derived from prompt content.
- Fix: record a real SHA-256 `prompt_hash` plus a separate `prompt_source_id`
  label; `test_prompt_hash_changes_when_prompt_content_changes` proves the hash
  is content-derived (`b2694db`).
- Invariant gap exposed: FR-E2 manifest integrity — provenance fields must not
  overstate what they prove.
