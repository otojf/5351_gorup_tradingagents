# AAPL — Fundamental Research Report (Point-in-Time as of 2026-11-11)

**Important data caveats up front:** The fundamentals vendor withheld profile data (market cap, P/E, sector, 52-week range, name) for this date because those fields only reflect *today's* quote rather than 2026-11-11, and it withheld insider transactions because it can't date-stamp filings. All figures below come from **SEC EDGAR statements filed on or before 2026-11-11**, at values *as filed then*. As a result, I can build a rigorous history of the P&L, balance sheet and cash flow, but I **cannot compute valuation multiples or assess insider sentiment** — traders should pair this with a live quote and a Form 4 feed. Note that the income and cash-flow series use a fiscal calendar where the quarter ending in late December is labeled as "Q1 of the *following* year" — I flag this where relevant.

---

## 1. Company identification
- **Ticker:** AAPL — Apple Inc. (resolved identity; not disproven by any tool result).
- Latest reported period available: **quarter ended 2026-06-27** (fiscal Q3 2026 under Apple's Sept fiscal year-end).
- Note: the most recent fiscal year-end balance-sheet date is **2026-09-26**, which is *after* the June quarter's P&L. This suggests the FY2026 10-K was filed by 2026-11-11, but the income/cash-flow extract provided does not include the September-2026 quarter. Treat September-quarter revenue/EPS as **unavailable** in this dataset.

## 2. Revenue and profit trajectory (quarterly, $M)

**Fiscal 2026 (to date):**
| Quarter ended | Revenue | Gross Profit | Gross Margin | Operating Income | Op Margin | Net Income | Net Margin | Diluted EPS |
|---|---|---|---|---|---|---|---|---|
| 2025-12-27 | 143,756 | 69,231 | 48.2% | 50,852 | 35.4% | 42,097 | 29.3% | $2.84 |
| 2026-03-28 | 111,184 | 54,781 | 49.3% | 35,885 | 32.3% | 29,578 | 26.6% | $2.01 |
| 2026-06-27 | 109,417 | 54,770 | 50.1% | 35,695 | 32.6% | 29,789 | 27.2% | $2.02 |

**Year-over-year comparison (same fiscal quarters prior year):**
| Quarter ended | Rev 2026 | Rev 2025 | YoY Growth | NI 2026 | NI 2025 | YoY |
|---|---|---|---|---|---|---|
| Dec quarter | 143,756 | 124,300 | **+15.7%** | 42,097 | 36,330 | **+15.9%** |
| Mar quarter | 111,184 | 95,359 | **+16.6%** | 29,578 | 24,780 | **+19.4%** |
| Jun quarter | 109,417 | 94,036 | **+16.4%** | 29,789 | 23,434 | **+27.1%** |

**Key insight:** AAPL is re-accelerating from its 2024–2025 trough. Revenue growth of low-to-mid teens is roughly **double** the ~7–8% growth seen in FY2024–2025, and net income is growing faster than revenue (Jun-26 net income +27% YoY), implying **operating leverage**. The most recent two quarters show essentially **flat sequential revenue** (111.2B → 109.4B) but a **gross-margin expansion to 50.1%** — a two-year high. This is the highest gross margin in the entire provided series back to 2016. That combination (flat volume, rising margin) tells traders the earnings beat is **mix/pricing/quality-of-revenue driven, not unit-volume driven** — typically a positive, durable signal, but it also means upside now depends on sustaining margin rather than acceleration.

**Historical context on gross margin (dilution from AI-scale):**
- FY2016 low: ~40% (e.g., 2016-06-25: 16,106/42,358 = 38.0%)
- 2020–2023: mid-40s
- FY2025: ~46–47%
- FY2026: **48–50%** — a clear structural step-up.

If the shift is toward high-margin services/App Store-type revenue, margin should hold; if it's tariff/tariff-refund timing or a one-off mix, it will mean-revert. **Actionable check:** compare next quarter's gross margin to the 50.1% print — a sub-48% reading would suggest normalization and likely pressure the multiple.

## 3. Balance sheet and capital structure

**Latest (2026-09-26):**
| Metric | Value ($M) |
|---|---|
| Total Assets | 404,548 |
| Current Assets | 173,857 |
| Cash & Equivalents | 36,305 |
| Total Liabilities | 292,455 |
| Current Liabilities | 169,915 |
| **Stockholders' Equity** | **112,093** |

**Trend highlights:**
- **Equity rebuilt sharply:** $65.8B (Jun-25) → $73.7B (Sep-25) → $112.1B (Sep-26). That's a **~70% increase in a year** — a direct consequence of enormous buyback-funded net income outrunning buybacks (see §4). Book value is now at its highest level in the provided series (surpassing the 2012-era peak of ~$118B territory at ~$112B adjusted).
- **Current ratio improvement:** 173,857 / 169,915 = **1.02** at Sep-26, versus 0.85 at Jun-25 (122,491/141,120) and 0.88 at Dec-25 (158,104/162,367). Liquidity is the best in recent quarters — a positive for debt-servicing credibility and for financing flexibility.
- **Net cash position (cash minus total debt is not fully derivable** since debt is not separately reported**, but treating all liabilities as not debt gives true cash of $36.3B plus securities not shown). The current liabilities jump to $169.9B from $149.3B in Jun-26 is worth watching — drivers could be commercial paper, accrued taxes or seasonal payables; any debt build-up here would shrink the net-cash cushion.
- **Asset growth of +18% YoY** ($331.5B Jun-25 → $383.3B Jun-26) is faster than revenue growth — the balance sheet is expanding with cash and presumably marketable securities, consistent with retained earnings growth.

## 4. Cash flow — the strongest part of the story

**Fiscal 2026 to date (9 months ended 2026-06-27):**
| Metric | 9M FY2026 | 9M FY2025 | YoY |
|---|---|---|---|
| Operating Cash Flow | **116,996** | 81,754 | **+43.1%** |
| Capex | 6,799 | 9,473 | −28.2% |
| **Free Cash Flow** | **~110,197** | ~72,281 | **+52.4%** |
| Investing CF | −18,811 | +17,782 | swing to outflow |
| Financing CF | −94,575 | −93,210 | slight larger outflow |

**Key insights:**
1. **FCF is compounding far faster than earnings.** CFO +43% versus net income +~20% — a huge quality signal. The gap implies **working-capital release** (likely payables/receivables timing) and lower capex. Working-capital-driven FCF is not infinitely repeatable; expect normalizing CFO in FY2027.
2. **Capex is down 28% YoY** to $6.8B against $110B of FCF — a **capex intensity of just ~6% of revenue**. AAPL is *not* a heavy capex AI-builder at the core level in this dataset. This is a contrast with hyperscalers and is the main reason its FCF conversion is elite. **Risk:** if AI infrastructure spending is flowing through *partner* balance sheets rather than Apple's, the company's competitive position could be more dependent on third parties than the cash flow implies.
3. **Investing cash flow swung to an $18.8B outflow** from a $17.8B inflow last year — a ~$36B swing. This is likely marketable-securities purchases; it does not necessarily represent capital destruction, but it explains why the **cash balance fell from $45.3B (Dec-25) to $36.3B (Sep-26)** despite record FCF. Traders should verify against the 10-Q "purchases of marketable securities" line before concluding cash is being consumed.
4. **Financing outflow of ~$94.6B over 9M** (buybacks + dividends) is $17–18B *less* than the previous year's $93.2B — roughly in line, but net of the higher FCF, Apple is now **retaining more cash** and building equity (consistent with §3). This is a subtle but important shift: buyback *intensity* (as % of FCF) may be flattening.

## 5. Valuation and profitability framework (what I can infer)

Without a live quote I cannot give a P/E. But from EPS: trailing four quarters = Jun-26 $2.02 + Mar-26 $2.01 + Dec-25 $2.84 + Jun-25 $1.57 → **TTM EPS ≈ $8.44**; if the Sep-26 quarter is similar to Sep-25 (≈$1.6–1.8), TTM EPS is likely **~$10.0–10.3**. Annualizing Q3-26 EPS ×4 gives ~$8.1, which understates seasonality (Q1 is the strongest quarter). **Actionable:** use TTM EPS of ~$10 and the trader's own market price to compute P/E; compare to the ~25–30x historical band. Given +16% growth and accelerating margins, a multiple at or below the historical band would be attractive.

**Profitability summary (fiscal 2026 nearest quarter):**
- Gross margin 50.1% (record in series)
- Operating margin 32.6% (vs. 36.6% in Dec-25, showing seasonal Q1 strength; vs. 30.0% in Jun-25 — up ~260bp YoY)
- Net margin 27.2%
- ROE (annualized on Jun-26 quarter): 29,789×4 / 107,520 ≈ **111%** — extremely high, but powered by a small equity base from years of buybacks. The rising equity base (now $112B) will mathematically **compress reported ROE** over time; do not read that as deteriorating business quality.

## 6. Insider transactions
**Withheld by the vendor for 2026-11-11** (no filing dates available, so it cannot guarantee point-in-time accuracy). I have **no insider signal** to incorporate. Traders should pull Form 4 data directly.

## 7. Red flags / items to verify
1. **Sep-26 quarter P&L missing** despite a Sep-26 balance sheet — confirm the FY2026 full-year revenue/EPS from the 10-K before acting on annual growth math.
2. **Current liabilities +$20.6B QoQ** to $169.9B — check for commercial paper / term debt issuance.
3. **Investing outflow and cash drawdown** — confirm it's securities, not M&A or losses.
4. **FCF quality** — CFO growth (+43%) outrunning net income (+20%) suggests working-capital benefits that will not repeat; do not extrapolate FY2026 FCF growth into FY2027.
5. **Margin sustainability** — 50.1% gross margin is the single most important forward metric; it is the least certain line in the model.
6. **Missing vendor data** — no valuation, no profile, no insider data. Any recommendation must be completed with a live quote.

## 8. Trader takeaway
The reported fundamentals for AAPL as of 2026-11-11 are **strongly constructive**: revenue re-accelerated to mid-teens growth (double the prior two years), margins hit a series high at 50%+, net income is compounding faster than sales, free cash flow is up >50% YoY, net equity is rebuilding, and the current ratio is the best in years. The primary risks are **margin mean-reversion, working-capital-driven FCF quality, and a rising current-liability balance**. With TTM EPS ~$10 and ~16% growth, AAPL screens as a high-quality compounder whose next catalyst is the September-quarter print and FY2027 margin guidance — absent a live multiple, my stance is **constructive on fundamentals, pending valuation confirmation**.

---

## Key Points Summary

| Category | Metric | Latest (as of 2026-11-11) | YoY / Trend | Signal |
|---|---|---|---|---|
| Revenue | Q ended 2026-06-27 | $109,417M | +16.4% YoY | Positive — re-acceleration |
| Revenue | Dec-25 quarter (Q1 FY26) | $143,756M | +15.7% YoY | Positive |
| Gross Margin | Jun-26 quarter | 50.1% | ~+29% two-yr high, highest in series | Strongly positive, watch durability |
| Operating Margin | Jun-26 quarter | 32.6% | ~+260bp YoY | Positive |
| Net Income | Jun-26 quarter | $29,789M | +27.1% YoY | Strongly positive |
| Diluted EPS | Jun-26 quarter | $2.02 | vs $1.57 YoY | Positive |
| TTM EPS (est.) | ~$10.0–10.3 | vs. ~$8.4 four-qtr sum | Rising | Positive |
| Total Assets | 2026-09-26 | $404,548M | +13% vs Jun-25 | Positive |
| Stockholders' Equity | 2026-09-26 | $112,093M | +70% YoY (+$46B) | Strongly positive |
| Current Ratio | 2026-09-26 | 1.02 | 0.85 → 1.02 | Improving |
| Current Liabilities | 2026-09-26 | $169,915M | +$20.6B QoQ | Caution — verify |
| Operating Cash Flow | 9M FY2026 | $116,996M | +43.1% YoY | Strongly positive |
| Free Cash Flow | 9M FY2026 | ~$110,197M | +52.4% YoY | Strongly positive (WC-boosted) |
| Capex | 9M FY2026 | $6,799M | −28.2% YoY (~6% of sales) | Positive for FCF; AI-competitiveness question |
| ROE (annualized) | Jun-26 | ~111% | High but will compress | Neutral |
| Insider Transactions | — | Withheld by vendor | n/a | No signal available |
| Valuation / Market Cap | — | Withheld by vendor | n/a | Must use live quote |