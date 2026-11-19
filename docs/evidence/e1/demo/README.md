# NFR-E1 Demo — Reproducible Offline Evaluation (Placeholder)

This folder will reproduce the NFR-E1 behaviour on deterministic local data using
the real `eval/` harness: no network, no external API, no LLM call.

Planned contents (Phase 3/4):

- `run_demo.py` — runs the 3-case golden set and writes the before/after table.
- `demo-output.txt` — the verbatim captured output (3 case rows; real token
  difference between the two sides).
- `compare.csv` / `compare.md` — the generated comparison table.

## How it will be reproduced

```bash
python docs/evidence/e1/demo/run_demo.py
```

Status: PLACEHOLDER — wired up in Phase 3 (3-case compare) / Phase 4 (capture).
