# Project Status (stable memory)

This file is my persistent notes. If the session resumes, this is
what I remember.

## User profile
- HKU COMP2501 (Section 1SH, 2026) student.
- macOS, no brew, Node 24, R 4.2.3, Python 3.13.7.
- Project: "The Sound of a Decade: Multi-Platform Audio-Embedding Analysis of Chinese Popular Music Taste, 2015-2025".
- Style: short, direct, in Chinese.
- Out-of-scope by user (declared 2026-10-02):
  * audio embeddings (MERT / Jukemir / CLAP / librosa)
  * slides (PPT / reveal.js) — to be done later, not now
  * NetEase / Kugou / Douyin / Bili / Last.fm (proposal-named platforms) — we tried each, kept 2

## Final scope (what we DO have):
1. **QQ Music**: 7 toplists × weekly issues, 2018W30 - 2024W52 (~137K rows).
   - topIds: 26 (热歌榜), 28 (网络歌曲榜), 5 (内地榜), 57 (电音), 58 (说唱), 60 (抖音), 65 (国风)
   - Changepoints at 2019, 2020, 2022 (p<0.001, BIC + permutation test)
2. **NetEase current snapshot**: today's top 200, used as the China comparison
3. **Apple Music CN + US current snapshots**: 50 + 50 songs, used for cross-region structural metrics
4. **R analysis pipeline 00_smoke + 01_clean ... 17_cross_region_patterns** (15 R scripts)
5. **R Markdown HTML report**: `R/report.html`

## KEY FINDINGS (must appear in proposal and report):

### QQ internal conclusions:
- 7 charts, ~137K rows.
- **2019 / 2020 / 2022 changepoints** (BIC + permutation, p<0.001).
- Cross-chart correlation:
  - Hot Songs ↔ Online Songs: 0.92 (strong sync)
  - Hot Songs ↔ Guofeng: 0.72
  - Hot Songs ↔ Rap: **-0.89** (anti-sync)
  - Hot Songs ↔ Douyin Hit: **-0.76** (anti-sync, post-2022)
- Genre drift 2020-2024:
  - rap 0.39 -> 0.36
  - edm 0.27 -> 0.41
  - guofeng 0.34 -> 0.24
- "Most average" songs per year (national anthems):
  - 2019《心如止水》Ice Paper
  - 2020《世界这么大还是遇见你》程响
  - 2021《白月光与朱砂痣》大籽
- LOF vs Euclidean outlier detection: ~0 overlap, both methods give
  complementary signals.

### COVID-2020 (QQ data only, no external narrative):
- pre_covid    (73 weeks): 280 unique songs / week, 84.7 new songs / week
- covid_q1     (14 weeks): 240 / 61.5 (industry contraction)
- covid_recovery (9 weeks): 278 / 85.1 (back to baseline)
- post_covid   (26 weeks): 440 / 120 (1.5x baseline surge)
- The 2020 changepoint is best interpreted as the post-lockdown
  acceleration, not the lockdown itself.

### Cross-region structural findings (current snapshots):
- Apple Music CN: 84% of top 50 are 1996-2018 songs (Jay Chou era)
- Apple Music US: 20% of top 50 are 2018+ songs (recent)
- Spotify Global: cannot compute (no release_date in RSS feed)
- QQ: 18.9% of top 200 are 2018+ songs (mix of new + old)
- NetEase: 50.6% of top 200 are 2018+ songs (skewed toward old)
- Artist concentration (Gini): all platforms ~0.32
- Top-3 artist share: Apple Music CN 54% (Jay Chou dominant),
  Apple Music US 38%, QQ 24.5%, NetEase 9.1%
- KEY INSIGHT: "Old catalogue" + "star concentration" are MORE
  extreme on Apple Music CN than on QQ. QQ's "old songs still
  chart" and "2022 split into Douyin-driven and QQ-driven streams"
  are QQ-platform patterns, not Chinese-market patterns.

### 2019 / 2020 / 2022 ↔ real-world events (CRITICAL, user said remember):
| Year | Real event | QQ observation | External corroboration |
|------|-----------|---------------|------------------------|
| 2019 | Douyin DAU ~400M, becomes dominant music-discovery; QQ launches Douyin Hit chart (topId=60) | New chart-volume regime; new sub-charts enter corpus | Wikipedia "Douyin / TikTok" + user-curated decade-canon playlists (removed from final repo) |
| 2020 | COVID-19 nationwide lockdown (Jan-Apr); home consumption; 15s short-loop BGM intensifies | Industry contraction in 2020-Q1; post-lockdown surge in 2020-W27+ | Wikipedia "COVID-19 pandemic in mainland China" + Wikipedia "Douyin/TikTok" + Spotify Wrapped 2020 |
| 2022 | Guofeng & Douyin sub-charts solidify; QQ launches Guofeng Hot Songs (topId=65); Shanghai lockdown | Cross-chart correlation flips: Hot ↔ Douyin r=-0.76 | Wikipedia "Music of China" |

### Hypothesis status:
- H1 (drift): ✅ confirmed
- H2 (changepoints): ✅ confirmed (2019/2020/2022)
- H3 (platform asynchrony): ✅ confirmed (QQ internal 7-chart split into 2 clusters post-2022; cross-region CN/US 0% overlap)
- H4 (homogenisation): ❌ NOT supported. OPPOSITE: platform specialisation post-2022

## Out of scope (do NOT touch unless user re-opens)
- audio mp3 download
- All AI audio embeddings (MERT / Jukemir / CLAP / librosa)
- PPTX / reveal.js slides (user said "later")
- Per-song play counts (QQ code=500003)

## Final pipeline (in `pipeline/`):
- `qq_official/fetch_qq_toplist.py` — 7 toplists × ~340 weekly issues
- `qq_official/rebuild_csv_from_cache.py` — re-derive CSV from cached JSON
- `qq_official/fetch_current_snapshot.py` — current top 200 for cross-region
- `netease_official/fetch_current_toplist.py` — current NetEase top 200
- `apple_music_official/fetch_current_charts.py` — Apple Music CN / US top 50

## Final R scripts (in `R/`):
- `00_smoke.R` (sanity check)
- `01_clean.R` (raw CSV -> song-year summary)
- `02_yearly_summary.R` (per-year aggregates; renamed from `02_pca.R`)
- `03_umap.R` (t-SNE on chart-history features)
- `04_special_songs.R` (per-year most-average / most-outlier Euclidean)
- `05_changepoint.R` (BIC + permutation, detects 2019/2020/2022)
- `06_toplist_compare.R` (QQ hot vs QQ online alignment)
- `07_version_normalize.R` (regex live/cover/remix/draft flagging)
- `08_topid_overview.R` (7-chart correlation matrix)
- `09_genre_drift.R` (rap / edm / guofeng share over time)
- `14_lof_outliers.R` (LOF vs Euclidean outlier comparison)
- `15_covid_qq_features.R` (covid_q1 vs post_covid QQ features)
- `17_cross_region_patterns.R` (cross-region structural metrics: share_old, gini, top3)

## Documentation (in `docs/`):
- `PROJECT_STATUS.md` (this file)
- `FINDINGS_INTERPRETATION.md` (2019/2020/2022 ↔ real events)
- `CROSS_PLATFORM_NOTES.md` (5-platform feasibility matrix, what was tried and rejected)
- `DATA_DICTIONARY.md` (every CSV/JSON column documented)
- `data_acquisition_methodology.md` (why Python for fetch + R for analysis)

## Key documents at top level:
- `PROPOSAL_QQ_DATA_SECTION.md` (drop-in for proposal section 4-5)
- `START_HERE.txt` (one-page guide)
- `README.md` (project overview)
- `renv.lock` (69 R packages locked)