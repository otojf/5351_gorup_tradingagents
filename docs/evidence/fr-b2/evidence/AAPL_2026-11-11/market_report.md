# AAPL — Technical Analysis Report (as of 2026-11-11)

## 1. Executive Summary

AAPL closed at **355.63** on 2026-11-11, a fresh high for the visible window and the strongest close since 2026-07-29 (337.90). The stock is in a **confirmed, structurally intact uptrend** (price > 50-SMA > 200-SMA), recently exited a six-week sideways consolidation, and has just produced a **fresh MACD bullish crossover**. Options positioning is constructive but not yet stretched (RSI 60.4), while volatility has expanded materially (ATR 8.66 vs ~6.2–6.7 in mid-October) — this is a "trend continuation" setup with elevated risk, not a low-risk entry.

All exact figures below are sourced from the verified market snapshot at 2026-11-11; no conflicts between the raw OHLCV feed and the snapshot were found (the 2026-11-11 row matches exactly: O 349.55 / H 355.91 / L 349.33 / C 355.63 / V 34.28M).

---

## 2. Indicator Selection & Rationale

I selected **8 complementary indicators** spanning trend, momentum, volatility, and volume — deliberately avoiding redundant pairs (no stochrsi alongside RSI, no Bollinger upper band standalone since the verified band values are already captured):

| Category | Indicator | Why selected for this context |
|---|---|---|
| Trend (long) | `close_200_sma` | Confirms the strategic regime; persistent upward slope signals a durable bull structure |
| Trend (medium) | `close_50_sma` | Defines the "line in the sand" for the current pullback/consolidation; useful for stop placement |
| Trend (short) | `close_10_ema` | Captures the sharp post-3rd-November re-acceleration faster than the SMAs |
| Momentum | `macd` + `macds` + `macdh` | Full MACD complex: needed because the crossover is *fresh* (1 day old) and histogram direction matters more than level |
| Momentum (filter) | `rsi` | Guards against chasing into overbought; currently shows there's still headroom |
| Volatility/mean-reversion | `boll` (middle) + `boll_lb` | Envelope position and squeeze/expansion read; middle band doubles as dynamic pivot |
| Risk | `atr` | Essential given volatility just expanded ~30%; sets stop distance and position size |
| Volume | `vwma` | Tests whether price strength is volume-backed — critical after the 2026-11-04 volume spike |

---

## 3. Trend Structure — Strong and Stacked

The moving average stack is cleanly bullish and **expanding**:

- **Close:** 355.63
- **10 EMA:** 347.08 (price is **+8.55 above** it, ~2.5% premium)
- **50 SMA:** 337.88 (price is **+17.75 above**, ~5.3%)
- **200 SMA:** 300.01 (price is **+55.62 above**, ~18.5%)

Key observations:

1. **All three averages are rising day-by-day.** The 50-SMA has climbed from 323.00 on 2026-10-12 to 337.88 on 2026-11-11; the 200-SMA from 290.75 to 300.01 over the same window. There is no flattening or roll-over — this is a genuinely advancing structure, not a stalling one.
2. **The 50/200 spread is widening** (37.87 today vs 32.25 on 2026-10-12), meaning medium-term momentum is accelerating relative to the long-term baseline. No death-cross risk is remotely in play.
3. **Price is at the top of the stack, not the bottom** — buyers are paying a premium to every average. That's trend strength, but it also means the *distance to support* is large: an air-pocket to the 10-EMA (−2.4%) and then the 50-SMA (−5.0%) exists if sentiment flips.

**Caveat on the "new high":** The 355.63 close is the highest close *in this dataset's window*, but there is a **precedent at a higher intraday level** worth flagging: 2026-11-05 printed a high of 355.38 and 2026-11-04 a high of **354.50** on huge volume, while the last clear structural peak on the chart is 2026-10-23's **351.73** high / 348.91 close on 2026-10-29. Today's 355.91 intraday high clears all of these, but only modestly — this is a **marginal breakout, not a decisive one**, and deserves confirmation on a closing basis before being treated as a durable trend leg.

---

## 4. Momentum — MACD Just Flipped; RSI Has Room but Is Not Cheap

This is the most interesting part of the analysis, because the momentum picture changed **in the last 24 hours**.

### MACD complex (the crossover is one day old)
| Date | MACD | Signal | Histogram |
|---|---:|---:|---:|
| 2026-10-23 | 4.375 | 4.060 | +0.314 |
| 2026-10-29 | 4.062 | 4.066 | −0.004 |
| 2026-11-02 | 3.023 | 3.813 | −0.789 |
| 2026-11-03 | 1.879 | 3.426 | **−1.547** (trough) |
| 2026-11-06 | 2.069 | 2.838 | −0.769 |
| 2026-11-10 | 2.692 | 2.760 | −0.068 |
| **2026-11-11** | **3.355** | **2.879** | **+0.476** |

Interpretation:
- The MACD line peaked around 2026-10-23 (4.375) and rolled over, triggering a **bearish crossover around 2026-10-29** (histogram crossed to −0.004) which deepened into a −1.547 trough on 2026-11-03 — coinciding with the low-close of 331.90 that day.
- Since then the histogram has **climbed for six consecutive sessions** (−1.547 → −0.848 → −0.736 → −0.769 → −0.245 → −0.068 → **+0.476**), and on **2026-11-11 the MACD line crossed back above the signal line**.
- **Nuance:** because the MACD *level* (3.355) is still well below its October peak (4.375), this is a **re-acceleration within an intact uptrend**, not a fresh emerging trend. A bullish crossover that occurs above the zero line is a continuation signal — historically more reliable than a zero-line cross — but it is only one day old and vulnerable to whipsaw, particularly given the choppy 344–350 range that persisted from mid-October through early November.

### RSI — constructive, not extended
- RSI is **60.42**, up sharply from **41.70 on 2026-11-03** and **51.46 on 2026-11-06**.
- This places it **below the 70 overbought threshold** and below the 63–65 readings seen in late October (63.93 on 2026-10-23, 64.76 on 2026-10-22). **There is genuine headroom** before momentum becomes a contrarian risk.
- Importantly, RSI did *not* make a lower low despite the price making a lower low on 2026-11-03 — a mild positive divergence pattern, though I would not over-weight a single reading.
- The risk: RSI rose from 41.7 to 60.4 in six sessions (+18.7 points). Short-term RSI can overshoot quickly at this velocity; a cool-off pause around 55–60 would be healthy.

---

## 5. Volatility & Bollinger Bands — Expansion Regime

- **ATR:** 8.66, up from 6.16 on 2026-10-28 and 6.97 on 2026-11-02. That is roughly a **40% expansion in daily true range** in about two weeks. Volatility is now genuinely elevated.
- **Bollinger middle (20-SMA):** 344.87 — rising steadily (335.78 on 2026-10-12 → 344.87 now), confirming the medium-term drift.
- **Bollinger lower:** 334.72. (The upper band from the snapshot is 355.01.)
- **Position:** the close of **355.63 is essentially at the upper band (355.01)** — price is pinned to the top of the envelope, closing marginally *above* it.

How to read this:
1. **Price riding/closing above the upper band is a breakout signature, not automatically an overbought sell.** In strong trends, AAPL can "walk the band" for days. The important confirmation is volume and follow-through (see §6).
2. The **band width has widened materially** — from a lower band of 328.67 (2026-10-12) to 334.72 now, while the middle rose only ~9 points. That is a **volatility expansion from a squeeze/consolidation**, which is exactly what you want to see on a breakout attempt.
3. **The ATR expansion cuts both ways.** It validates the breakout's energy, but it also means a routine 1-ATR adverse move is now ~8.7 points — enough to blow through a tight stop. Position sizing must be recalculated; stops placed within 1 ATR of entry on AAPL today are statistically likely to be hit by noise alone.

---

## 6. Volume — The Weakest Link in the Bull Case

The `vwma` (volume-weighted 20-day average) is **344.78**, up gently from 335.30 on 2026-10-02. That is a slow, orderly climb — no distribution signature, which is supportive.

**However, there is a critical divergence to flag:**

| Date | Close | Volume | Note |
|---|---:|---:|---|
| 2026-11-03 | 331.90 | 63.16M | Capitulation low close |
| **2026-11-04** | **349.51** | **89.64M** | Huge gap-up reversal (+5.3% off prior close) on the biggest volume in weeks |
| 2026-11-05 | 344.17 | 75.68M | Heavy volume, price fell |
| 2026-11-06 | 342.37 | 44.70M | |
| 2026-11-09 | 350.69 | 48.75M | |
| 2026-11-10 | 348.51 | 29.76M | Lightest volume in the recent window |
| **2026-11-11** | **355.63** | **34.28M** | **Breakout close on below-average volume** |

**The breakout to 355.63 was achieved on 34.28M shares — roughly 55% of 2026-11-04's 89.64M and below the 20-day VWMA-implied average.** The 2026-11-04 session did the heavy lifting (the gap-up reversal), but the price has since ground higher on **declining volume**. This is a classic warning sign: **price confirming while participation fades**. It is not disqualifying — Thanksgiving-adjacent and pre-weekend sessions often run light — but it lowers conviction in the breakout's durability.

**Also note:** the 2026-11-04 session printed a **high of 354.50 and 2026-11-05 a high of 355.38**; the stock then spent three sessions (Nov 5, 6, 10) failing to close above ~351. Today's 355.63 close finally cleared that shelf, but only by ~4.25 points, and on light volume. A single light-volume close does not yet constitute confirmation.

---

## 7. Actionable Interpretation for Traders

### For trend-followers (long bias)
- **The structural case is positive:** stacked and rising MAs, a fresh MACD bullish crossover above zero, RSI with headroom, and volatility expansion accompanying a breakout attempt. The path of least resistance remains up.
- **The confirmation standard should be raised** given the volume divergence. Rather than chasing at 355.63, consider requiring **one to two additional closes above ~355 with volume re-expanding above ~50M** as the trigger for adding exposure.
- **Dynamic support ladder** (all from verified data): **10-EMA 347.08** → **Bollinger middle 344.87 / VWMA 344.78** (converging, so a strong confluence shelf near 344–347) → **50-SMA 337.88**.

### For risk management (essential given ATR 8.66)
- A sensible invalidation for the breakout thesis sits **below the 344–347 confluence** (Bollinger middle/VWMA/10-EMA cluster) — roughly **1.0–1.3 ATR** below the current close, which is appropriately wide for the new volatility regime.
- A trend-level stop belongs **below the 50-SMA at 337.88**, i.e., ~1.8 ATR below. Anyone using a stop 4–5 points away is likely to be stopped out by ordinary noise.
- **Reduce position size** relative to October levels: ATR has expanded ~40%, so maintaining constant dollar-at-risk requires ~30% smaller positions at this price.

### For mean-reversion / short-term traders
- Price is **at/just above the upper Bollinger band (355.01)** with ATR elevated — statistically a poor *chase* point. A pullback to the **347–345** zone (10-EMA/VWMA/Bollinger middle) would offer a much better risk-defined entry with the trend.
- A close back **below 344.7** (Bollinger middle) would be the first evidence that the 2026-11-11 breakout failed and the stock is returning to the 338–350 chop that dominated October.

### Bear case / what would change the picture
- **MACD crossover fails** — histogram rolls back negative within 1–3 sessions (as happened around 2026-10-29 and 2026-10-21, both whipsaw points in October).
- **Failure below 351** — a close back into the 344–350 range would confirm the breakout was a light-volume fake.
- Volume stays below ~40M on any further advance, indicating the move is thin rather than demand-driven.

---

## 8. Key Levels Summary (verified 2026-11-11)

| Level | Value | Role |
|---|---:|---|
| Intraday high 2026-11-11 | 355.91 | Immediate resistance / breakout line |
| Bollinger upper band | 355.01 | Overbought / walk-the-band zone |
| **Close 2026-11-11** | **355.63** | Current price |
| 10 EMA | 347.08 | First dynamic support |
| Bollinger middle / VWMA | 344.87 / 344.78 | Confluence support shelf |
| 50 SMA | 337.88 | Trend invalidation line |
| Bollinger lower band | 334.72 | Deep-support / oversold zone |
| 200 SMA | 300.01 | Strategic bull-market line |

---

## 9. Summary Table

| Dimension | Indicator | Current Reading (2026-11-11) | Signal | Confidence / Caveat |
|---|---|---|---|---|
| Long-term trend | close_200_sma | 300.01, rising | **Bullish** | Secure; price 18.5% above |
| Medium-term trend | close_50_sma | 337.88, rising (from 323.00 on 10/12) | **Bullish** | Stack widening — strengthening |
| Short-term trend | close_10_ema | 347.08, rising | **Bullish** | Price 2.5% above — slightly extended |
| Momentum trend | macd / macds | 3.355 vs 2.879 | **Bullish crossover (1 day old)** | Low confidence — fresh, level below Oct peak |
| Momentum thrust | macdh | +0.476 (from −1.547 on 11/03) | **Improving 6 straight sessions** | Slope is the signal; volatile |
| Momentum filter | rsi | 60.42 (from 41.70 on 11/03) | **Constructive, headroom to 70** | Rising fast; watch for >70 |
| Volatility / mean-reversion | boll / boll_lb | Middle 344.87, Lower 334.72, Upper 355.01 | **Expanding; price at upper band** | Breakout-signature, but poor chase entry |
| Volatility / risk | atr | 8.66 (from 6.16 on 10/28) | **Elevated (~40% expansion)** | Must widen stops, cut size |
| Volume confirmation | vwma | 344.78, rising slowly | **Mildly bullish** | **Divergence: 11/11 breakout on only 34.3M vs 89.6M on 11/04** |
| **Overall** | — | **355.63 close** | **Uptrend continuation, marginally confirmed** | Confirmed structure + fresh MACD flip, but thin breakout volume and volatility expansion argue for confirmation before adding risk |

**Bottom line:** AAPL is a **structurally sound uptrend** (price > 50-SMA > 200-SMA, all rising; MACD re-crossed bullishly; RSI at 60 with room) that has just attempted a breakout to 355.63. The **quality of that breakout is questionable** because volume has contracted sharply versus the 2026-11-04 reversal session, and price is pinned to the upper Bollinger band with ATR up ~40%. The highest-probability playbook is to **hold existing longs with stops below the 344–347 confluence (or 337.88 for trend-followers), avoid chasing at the band, and look for a pullback into 347–345 or a volume-confirmed follow-through above 355.91** before deploying new capital.