# FR-A1 Demo — Deterministic Risk Gate (Reproducible, Offline)

This folder reproduces the FR-A1 risk-gate behaviour on deterministic local data.
It uses the **real** implementation (`tradingagents.risk_gate`) and, for the
full-graph section, the repository's existing offline scripted-model test
infrastructure. There is **no network, no external API, and no LLM call**.

- `run_demo.py` — the runnable demonstration script.
- `demo-output.txt` — the verbatim captured output of running the script.

## How to reproduce

From the repository root:

```bash
python docs/evidence/fr-a1/demo/run_demo.py
```

Recommended environment note: the script pins the repository root on `sys.path`
so the full-graph section can import `tests.test_graph_end_to_end`. It needs only
the project's own dependencies (already required by the repository).

### Self-checking and exit codes

The script is **self-checking**, not just a printer:

- Each scenario A–G is printed **and** verified against its expected outcome; the
  full-graph section is verified too.
- Every check prints `check <id>: PASS|FAIL — <detail>`.
- It ends with a `SUMMARY: n/8 expectancy checks passed (...)` line and a final
  `RESULT:` line.
- **Exit code `0` only when all expectancy checks pass and the full-graph
  demonstration succeeds.** Any failed check — including a full-graph exception —
  prints the failure(s) under `FAILURES:` and returns exit code `1`. A raised or
  missing full-graph result is reported as a failure, never treated as success.

## What is shown

### Section 1 — adapter-level demonstrations

Calls `tradingagents.risk_gate.adapter.apply_gate(...)` directly with deterministic
`TraderProposal`, `PortfolioDecision`, and `risk_portfolio` inputs. For each case it
reports:

- original AI model rating (`model_rating`, preserved as evidence),
- **core rule verdict** (`risk_evaluation.verdict` — the policy outcome),
- **effective publication verdict** (`risk_verdict`),
- final public rating (`final_rating`),
- decision status,
- triggered / unknown rules,
- audit persistence result (a real JSON file written to a temporary directory).

| Case | Scenario | Expected outcome | Check id |
|---|---|---|---|
| A | Valid BUY with complete risk inputs | APPROVED / ACTIONABLE, `final_rating` = Buy | `check A` |
| B | BUY without stop-loss | REJECTED / BLOCKED, `final_rating` = REVIEW (R1 VIOLATED) | `check B` |
| C | BUY without portfolio snapshot | NEEDS_REVIEW / PENDING_REVIEW, REVIEW (R2/R3 UNKNOWN) | `check C` |
| D | Single-name concentration over 10% (12%) | REJECTED / BLOCKED (R2 VIOLATED) | `check D` |
| E | Conflicting sector classification | never APPROVED; non-actionable (R3 UNKNOWN) | `check E` |
| F | Audit persistence failure | writer invoked and raises; no actionable output, no audit written | `check F` |
| G | No audit destination (would-be APPROVED) | core APPROVED but downgraded to NEEDS_REVIEW / PENDING_REVIEW, REVIEW | `check G` |

Each row is asserted automatically; a mismatch fails the run (exit code 1).

### Section 2 — full-graph integration

Runs the real `TradingAgentsGraph` with the offline scripted model and a supplied
`risk_portfolio`, proving the decision boundary end-to-end (effective signal,
preserved `model_rating`, both structured objects retained). **A failure to run or a
mismatched result here is a failure (`check FG: FAIL`) and makes the script exit
non-zero** — it is never reported as success.

## Deterministic data

The portfolio fixtures are fixed, internally consistent books:

- Valid book: `portfolio_value = 1,000,000 = cash 830,000 + NVDA 20,000 + MSFT
  150,000`; NVDA target weight `0.05` → projected `50,000` (an affordable
  `+30,000` increase); projected Technology `= 170,000 - 20,000 + 50,000 =
  200,000` (20% ≤ 30%).
- Conflicting-sector book: real Technology `300,000` (30%); buying NVDA raises it
  to `350,000` (35%), while the supplied target sector is `Energy` — a conflict
  that must not be allowed to hide the concentration.

## Important distinctions

- **Core rule verdict vs publication verdict.** `risk_evaluation.verdict` is the
  policy outcome of the rules. `risk_verdict` is the *effective publication*
  outcome, which additionally requires a durable audit. Case G shows core rules
  APPROVED but publication NEEDS_REVIEW because no audit was written.
- **Durability caveat.** `persist_audit` writes and closes a JSON file; it does not
  `fsync`. This is file-write durability, not crash-level durability.
- No result in this document is fabricated; every value comes from running the
  real code (see `demo-output.txt`).
