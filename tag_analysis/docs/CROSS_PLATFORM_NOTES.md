# Cross-Platform Validation — Final State

This file is the **historical** record of every cross-platform
attempt we made and why each was kept or dropped. The current
cross-platform analysis in the report uses only:

- **NetEase** (current top 200, only)
- **Apple Music CN** (current top 50)
- **Apple Music US** (current top 50)

For the cross-region structural metrics in Section 9.2, see
`R/17_cross_region_patterns.R` and
`data/interim/cross_region_patterns.csv`.

## What we attempted and rejected

| Platform | Why attempted | Why rejected |
|---|---|---|
| **Spotify Global** (top 50 current) | Wanted a Western comparison point | `release_date` column is empty for the entire top 50; cannot compute old-catalogue share or artist concentration meaningfully. Spotify's historical chart API was deprecated in 2024. |
| **Spotify Charts (historical)** | Could have validated QQ's 2019/2020/2022 changepoints at weekly resolution | Endpoint `charts-spotify-com-service.spotify.com/auth/v0/charts/<alias>/<date>` returns 401/403 for historical dates without login. |
| **Wikipedia `<year>_in_Chinese_music`** (10 HTMLs) + Billboard China V Chart year-end tables (8 CSVs) | Public history of Chinese music per year | The Wikipedia articles are sparse (mostly "who released what album in what month"). Billboard China V Chart stopped being updated after 2018. No quantitative event data. |
| **NetEase user-curated decade playlists** (5 playlists, ~6 000 songs) | Hoped to give NetEase-side proxy for the 2019/2020/2022 changepoints | The 5 playlists' createTime cluster around 2018, 2019, 2022, 2025 — they suggest cultural-period signals but the inference ("NetEase user anticipates 11 months before QQ") was anecdotal and removed. |

## What we kept

- **NetEase current top 200** (playlist 3778678). The 40.5 %
  overlap with QQ current top 200 is documented but no longer
  used as the headline cross-platform result; the structural
  metrics in Section 9.2 are the headline instead.
- **Apple Music CN top 50** + **Apple Music US top 50** (current).
  These provide the "Chinese music market via Apple" vs "US music
  market via Apple" axis that the structural metrics compare.

## What we did not attempt at all

| Platform | Why |
|---|---|
| **Kugou** | No public JSON API for historical chart data |
| **Douyin (TikTok) music API** | HTTP 403 without the app's `X-Bogus` signature |
| **Bilibili Audio** | "Annual top songs" concept does not exist; the platform is video-first |
| **Last.fm** | Public chart API requires free API-key registration at `last.fm/api`; excluded from "publicly retrievable data" |
| **Apple Music (full global chart)** | Apple's RSS exposes only the 50 most-played songs per region, no historical archive |

## Compliance recap

All kept cross-platform work is metadata-only, public, no login.
No mp3 downloaded. No anti-bot bypass. Referer header set as a
normal browser would.