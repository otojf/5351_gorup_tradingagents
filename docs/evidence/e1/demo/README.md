# NFR-E1 Demo — Reproducible Offline Evaluation

This folder reproduces the NFR-E1 behaviour on deterministic local data using
the real `eval/` harness: no network, no external API, no LLM call.

Contents:

- `run_demo.py` — runs the 3-case golden set and writes the before/after table.
- `demo-output.txt` — the verbatim captured output (3 case rows; a real token
  difference between the two sides).
- `compare.csv` / `compare.md` — the generated comparison table.

The "before" side runs all four analysts (`market, social, news, fundamentals`);
the "after" side drops the sentiment analyst (`market, news, fundamentals`), so
every case shows a real token delta (−6.67% under the scripted source). Per-run
state logs, memory logs and cache are written to a throwaway temp dir, so only
the table and capture are kept here.

**Ratings show `REVIEW` by design.** The demo supplies no `risk_portfolio`, and
the integrated FR-A1 risk gate is fail-closed: without an account snapshot the
Portfolio Manager publishes `REVIEW` instead of the model rating. This is the
current default behaviour, not a regression. What the demo demonstrates is the
token delta between the two analyst sets; the rating column is intentionally
`REVIEW` on both sides.

## How to reproduce

```bash
python docs/evidence/e1/demo/run_demo.py
```

Status: `demo-output.txt` / `compare.csv` / `compare.md` are the real captured
output of the command above, run after the FR-A1 fail-closed gate was integrated
(ratings `REVIEW`, token delta −6.67%). This is a **scripted/offline** demo: it
uses scripted data and a scripted model, not real market data or a real LLM.
