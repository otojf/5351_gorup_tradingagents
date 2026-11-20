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

## How to reproduce

```bash
python docs/evidence/e1/demo/run_demo.py
```

Status: works as of 2026-11-20 (the three case rows and the −6.67% delta in
`demo-output.txt` are the real, captured output of the command above). This is
a **scripted/offline** demo: it uses scripted data and a scripted model, not
real market data or a real LLM.
