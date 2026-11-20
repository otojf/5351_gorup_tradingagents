# FR-B2 — verification record

Baseline: `main` at `46bde74` (TradingAgents v0.7.1). Feature branch: `feat/fr-b2-conclusion`.

## Approval and design trail

The work was approved in stages in the working session (full trail in
[`provenance.md`](provenance.md)):

1. Reproduction plan approved (pin v0.7.1, AAPL 2026-11-11, CityU DeepSeek gateway).
2. Baseline reviewed and accepted: real report + `snapshot.txt` + one traceable claim.
3. FR-B2 test design revised and approved: `source_id` / `source_line` /
   `expected_snippet`; `report_span` carries only line + snippet; six mixed samples;
   a separate `claim_not_found` test.
4. Implementation approved and produced.
5. Two review rounds added regression tests and fixes: bare line number →
   `claim_not_found`; unreadable evidence isolated to its claim; `--out` must not
   overwrite any input **including source-table evidence files** (exit code 2).

## Offline acceptance (no network, no model)

```
python -m pytest fr_b2/tests -q
12 passed
```

The 12 tests cover: the positive citation resolves to the report line and the
snapshot line; missing citation; malformed citation; unknown source; missing
evidence file; invalid locator (out of range); valid line whose text lacks the
expected snippet (`invalid_locator`); bare line number / empty snippet / non-int
line / missing span (`claim_not_found`); undecodable evidence isolated to one
claim with the valid citation still passing; `--out` equal to an input file and
`--out` equal to a registered evidence file both refused with the file unchanged.

## Real-case result (six samples)

```
python -m fr_b2.check_citations \
  --report docs/evidence/fr-b2/evidence/AAPL_2026-11-11/report/1_analysts/market.md \
  --sources fr_b2/sources.json \
  --claims fr_b2/claims.example.json \
  --out fr_b2/out/result.json
```

```
c1_valid              SUPPORTED  -> snapshot.txt:66 (report market.md:5, "| 2026-11-11 | 355.63 |")
c2_missing_citation   UNTRACEABLE (missing_citation)
c3_malformed_citation UNTRACEABLE (malformed_citation)
c4_unknown_source     UNTRACEABLE (unknown_source)
c5_missing_evidence   UNTRACEABLE (missing_evidence)
c6_invalid_locator    UNTRACEABLE (invalid_locator)
SUMMARY total=6 supported=1 untraceable=5
```

## Output-overwrite guard

`--out` pointed at the registered evidence file `snapshot.txt`: the CLI returns
exit code `2` and the file's SHA-256 is unchanged (byte-for-byte preserved).

## Evidence provenance

`evidence/AAPL_2026-11-11/` was produced by a real TradingAgents v0.7.1 run of
AAPL on 2026-11-11 (deepseek, `CS5351/DeepSeek-V4-Flash`) on the CityU gateway.
The `snapshot.txt` was obtained independently via the official
`build_verified_market_snapshot("AAPL","2026-11-11")` before the analysis, as
check evidence for the same run (`docs/evidence/fr-b2/evidence/AAPL_2026-11-11/`).


## PR #11 review follow-up — 2026-11-20

The author approved the follow-up after receiving the review document from
`k1160967796`. The review tests were added first (commit `04ad26f`). Before
implementation, five integrity tests failed and the existing exit-code behaviour
test passed. This round then added the verifier and the 25-file registry.

| Check | Result |
|---|---|
| `python -m pytest fr_b2/tests -q` | 18 passed |
| Default `python -m pytest -q` with FR-B2 collection enabled | 1,430 passed; 1 skipped; 1 deselected; 100 subtests passed |
| `ruff check .` | Passed |
| `python -m fr_b2.verify_evidence --manifest docs/evidence/fr-b2/evidence-sha256.json` | 25/25 files matched |
| Temporary evidence modified or removed | MISMATCH or MISSING detected |
| Integrity CLI on matching / changed / invalid manifest | Exit 0 / 1 / 2 |
| Original six-case citation CLI | total=6, supported=1, untraceable=5; exit 0 |

The citation command's exit code 0 records successful completion, including
UNTRACEABLE findings. Callers use the result JSON to inspect those findings.
The ambiguous conditional return was simplified to `return 0`.

The registry records integrity as of 2026-11-20, relative to the stored artifacts
in `f80b28d`. The capture description remains in provenance. No evidence file
was regenerated. The README and integration notes state the FR-B2 scope and
identify the E-owner central log / manifest integration work.
