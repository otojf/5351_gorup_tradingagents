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
