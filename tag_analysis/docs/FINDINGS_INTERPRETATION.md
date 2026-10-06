# Interpretation of 2019 / 2020 / 2022 Changepoints

This is a one-page add-on for the proposal / report discussion section.
Drop it into Section 8 of your proposal ("Research Question Discussion")
or Section 9 of the report ("Findings").

## What we observed

We detected three changepoints in QQ Music's weekly-chart behaviour:

- **2019** — the QQ chart-history enters a higher-volume, faster-cycling
  regime. Average unique songs per week rises; new sub-charts
  (Douyin Hit) appear in our dataset.
- **2020** — average weeks-on-chart plummets. The number of unique
  songs continues to grow but each song stays shorter.
- **2022** — cross-chart correlation structure flips: Hot Songs ↔
  Douyin Hit becomes strongly negative (r = -0.76). The Guofeng
  Hot Songs chart (topId=65) is introduced.

These three years were identified automatically by piecewise-linear
fitting + BIC + permutation test (`R/05_changepoint.R`), not chosen
by us. They reproduce in every cross-validation we tried.

## What was happening in Chinese popular music in those years

### 2019: the Douyin takeover

- Douyin's DAU reached ~400 million in mid-2019, becoming the
  dominant music-discovery channel.
- The QQ Hot Songs chart started to see a sharp rise in songs that
  had been popular on Douyin before trending on QQ.
- QQ Music launched the **抖音热歌榜 (Douyin Hit, topId=60)** as a
  separate sub-chart in 2019.

This explains why we observe 2019 as the entry-point of a new,
faster-cycling chart regime in our data: the cycle was being driven
by a 15-second short-video format.

### 2020: the pandemic short-loop effect

- COVID-19 nationwide lockdown (Jan-Apr 2020) led to a sustained
  period of in-home consumption.
- Listeners turned to short-video platforms (Douyin / Kuaishou) for
  music discovery.
- "BGM-ification" of songs intensified: songs that worked as 15-30
  second video loops became disproportionately prominent.

This matches our observation that **average weeks-on-chart plummeted
in 2020** while unique song count continued to climb. Songs got
more, but each lasted less.

### 2022: ecosystem split

- The Guofeng (国风) and Douyin sub-charts solidify into separate
  listener ecosystems.
- QQ Music introduces the **国风热歌榜 (Guofeng Hot Songs, topId=65)**
  as a separate chart.
- Cross-chart correlations sharpen: Hot Songs and Douyin Hit move
  into **strongly negative** correlation (r = -0.76).

This is the year our QQ chart-data says Chinese pop music's "single
mainstream" finally gave way to **two parallel streams** — a
Douyin-driven stream and a QQ-algorithm-driven stream — with little
shared audience.

## What this means for the proposal's research questions

- **Q1 (drift)**: ✅ confirmed — drift is real and concentrated at
  2019, 2020, 2022.
- **Q2 (synchronisation across platforms)**: ⚠️ partially confirmed —
  QQ internal 7 charts split into **two clusters** (Douyin-driven
  vs Hot-Songs-driven) starting 2022. NetEase shows ~60 % non-
  overlap with QQ today, but historical NetEase comparison is
  blocked by API limits.
- **H1 / H2 / H3 hypotheses**: ✅ all three are supported by QQ
  data. H4 (homogenisation) is not supported — in fact the *opposite*
  (platform specialisation) is observed post-2022.

## Sources

- QQ Music toplist data: this project's `data/raw/qq/`.
- NetEase mega-playlist "2015-2025 十年最全歌曲" (5545 songs):
  `https://music.163.com/playlist?id=13669065763`.
- Cultural context: industry reporting on Douyin DAU, COVID-19
  lockdowns, and Chinese pop-music history. These are widely
  documented in industry press (e.g. 36kr, Huxiu, QQ Music's own
  annual reviews); we cite them as general background rather than
  introducing new evidence.