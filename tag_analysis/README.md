+# The Sound of a Decade

HKU COMP2501 (Section 1SH, 2026) project: chart-history analysis of
Chinese popular music taste, 2018-2024, across seven QQ Music public
toplists.

## What is in here

### Pipeline (Python)
- `pipeline/qq_official/fetch_qq_toplist.py` -- weekly toplist collector
  that hits `https://u.y.qq.com/cgi-bin/musicu.fcg` (no login, no
  anti-bot). Pulls every honoured `period` for each topId.
- `pipeline/qq_official/rebuild_csv_from_cache.py` -- re-derives the
  long-format CSV from cached per-period JSON, useful when we add new
  columns without re-hitting QQ.
- `pipeline/netease_official/fetch_playlist.py` -- Netease public
  playlist collector (v6 trackIds + v3 song/detail); not used in this
  draft because the API does not expose weekly history.

### R analysis (sequenced)
- `R/00_smoke.R`         — first sanity plot on the raw CSV
- `R/01_clean.R`         — raw CSV → song-year summary
- `R/02_pca.R`           — year-over-year summary plot
- `R/03_umap.R`          — t-SNE of chart-history features
- `R/04_special_songs.R` — per-year "most average" / "most outlier"
- `R/05_changepoint.R`   — piecewise-linear changepoint detection +
  permutation p-value
- `R/06_toplist_compare.R` — two-chart (hot vs online) alignment
- `R/07_version_normalize.R` — regex-based live/cover/remix flagging
  + canonical version dedup
- `R/08_topid_overview.R` — cross-chart correlation matrix across all
  7 toplists
- `R/09_genre_drift.R`   — share of songs carrying each inferred
  genre (rap / edm / guofeng) over time
- `R/report.Rmd` → `R/report.html` — final HTML report (knit)

## Status

- [x] QQ 7 toplists × weekly issues, 2018W30 - 2024W52 (~137K rows)
- [x] R pipeline (01..09), all wired
- [x] cross-chart correlation matrix
- [x] changepoints 2019 / 2020 / 2022 (p<0.001)
- [x] most avg / outlier per year
- [x] inferred genre drift (rap / edm / guofeng)
- [x] canonical version dedup with live/cover/remix flags
- [x] final HTML report (R/report.html)
- [ ] audio embedding (out-of-scope per user)
- [ ] cross-platform NetEase / Kugou / Douyin (out-of-scope per user)
- [ ] slides (out-of-scope per user)

## Toplists pulled

| topId | Title | Genre tag | Issues | Unique songs |
|---|---|---|---|---|
| 26 | 热歌榜 (Hot Songs) | - | 202 | 1942 |
| 28 | 网络歌曲榜 (Online Songs) | - | 331 | 9626 |
| 5  | 内地榜 (Mainland) | - | 288 | 10928 |
| 58 | 说唱榜 (Rap) | rap | 195 | 3125 |
| 57 | 电音榜 (EDM) | edm | 191 | 2878 |
| 65 | 国风热歌榜 (Guofeng) | guofeng | 194 | 1303 |
| 60 | 抖音热歌榜 (Douyin Hit) | - | 167 | 1729 |

## Coverage caveat

QQ's `period` parameter is honoured only for **2018W30 .. 2024W52** on
topIds 26/28/5/58/57/65/60. The proposal said "2015-2025"; the actual
window is "2018-2024". 2015-2017 is not available through this
endpoint.

## Field caveat

QQ's per-song detail endpoint (genre, language, lyrics, play-counts) all
return `code=500003` without login since 2024+. We collect only the
fields returned by the public weekly toplist endpoint:

`top_id, top_title, period, rank, song_id, song_mid, song_title,
singer_name, singer_mid, album_mid, cover, song_type, rank_value,
rank_type, genre_inferred (only when chart is a genre chart),
chart_listen_num (per-issue aggregate), chart_update_time`.

## Reproduce

```sh
# 1. pull all 7 toplists (~5 min total, cached after first run)
for tid in 26 28 5 58 57 65 60; do
  python3 pipeline/qq_official/fetch_qq_toplist.py --topid $tid --density weekly
done

# 2. R analysis
Rscript R/01_clean.R
Rscript R/02_pca.R
Rscript R/03_umap.R
Rscript R/04_special_songs.R
Rscript R/05_changepoint.R
Rscript R/06_toplist_compare.R
Rscript R/07_version_normalize.R
Rscript R/08_topid_overview.R
Rscript R/09_genre_drift.R

# 3. knit report
PATH=$HOME/bin:$PATH Rscript -e 'rmarkdown::render("R/report.Rmd")'
open R/report.html
```

## Compliance

We never download mp3. We collect only chart metadata.
Per-song audio-level data is out of scope for this project.