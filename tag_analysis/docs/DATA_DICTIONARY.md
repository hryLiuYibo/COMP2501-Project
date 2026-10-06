# Data Dictionary

This file documents every CSV / JSON column used in the project.
Reviewers can cross-reference the schema here against any data
file in `data/raw/` or `data/interim/`.

---

## A. Raw QQ Music weekly toplists

### `data/raw/qq/qq_topId{N}_weekly_long.csv`

One row per `(topId, period, song, rank)` triple. ~137 000 rows
across seven topIds.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `top_id` | int | QQ toplist identifier | 26 |
| `top_title` | str | Chinese name of the chart | 热歌榜 |
| `period` | str | Week issued, `YYYY_WNN` | 2020_30 |
| `rank` | int | Position in the issue, 1-100 | 5 |
| `song_id` | int | QQ internal song id | 270029523 |
| `song_mid` | str | QQ URL-safe song identifier | 004d66am1tcht8 |
| `song_title` | str | Song name (may carry live / cover / remix markers) | 마리아 (Maria) |
| `singer_name` | str | Performing artist(s), comma-separated | 华莎 (화사) |
| `singer_mid` | str | QQ URL-safe artist identifier | 001aAX6V1QArFZ |
| `album_mid` | str | QQ URL-safe album identifier | 004d66am1tcht8 |
| `cover` | str | Album cover URL (often empty) | https://... |
| `song_type` | int | QQ internal song type | 0 |
| `rank_value` | str | Movement indicator ("12" = +12 / "-3" = -3) | "0" |
| `rank_type` | int | QQ internal movement type | 1 |
| `genre_inferred` | str | Inferred from genre-tagged chart membership | rap / edm / guofeng / "" |
| `chart_listen_num` | int | Total listen count for the *issue* (not per song) | 19400000 |
| `chart_update_time` | str | Issue update date (YYYY-MM-DD) | 2020-07-23 |
| `fetched_at` | date | When we collected it | 2026-10-02 |

### `data/raw/qq/qq_topId26_current_snapshot.csv`

Same schema as the weekly long CSV, but for the **current** top
200 (used in cross-platform comparison against NetEase).

---

## B. Raw NetEase public playlists

### `data/raw/netease/netease_hot_songs_3778678.csv`

The current NetEase Hot Songs chart (200 entries).

| Column | Type | Meaning | Example |
|---|---|---|---|
| `track_id` | int | NetEase internal song id | 1973665667 |
| `title` | str | Song name | 海屿你 |
| `artist` | str | Performing artist(s), comma-separated | 马也_Crabbit |
| `album` | str | Album name | 海屿你 |
| `year` | int | Song publish year (may be NA) | 2022 |
| `duration_ms` | int | Duration in milliseconds | 295940 |
| `playlist_id` | int | NetEase playlist id | 3778678 |
| `playlist_title` | str | Playlist name | 热歌榜 |
| `fetched_at` | date | When we collected it | 2026-10-02 |
| `source_url` | str | NetEase URL | https://music.163.com/song?id=... |
| `netease_update_time_ms` | int | NetEase last-update timestamp (ms) | 1790901750670 |
| `label` | str | Internal label we use | netease_hot_songs |

### (Other NetEase public playlists)

We initially collected 5 user-curated decade-canon playlists
(5 545 + 43 + 76 + 314 + 199 = 6 177 songs). They have been
removed from `data/raw/netease/` because the inference drawn
from their `createTime` timestamps ("NetEase user anticipates 11
months before QQ") was anecdotal. The schema was the same as
`netease_hot_songs_3778678.csv` minus the `netease_update_time_ms`
column. The collector script
`pipeline/netease_official/fetch_playlist.py` is also no longer in
the repo; if you want to re-collect, see the project history.

---

## C. Raw Apple Music current snapshots

### `data/raw/apple_music/apple_music_<region>_top50_*.csv`

Apple Music publishes a public RSS feed of the 50 most-played
songs per region at `rss.applemarketingtools.com`. We pull two
regions: `cn` (China) and `us` (United States). No historical
archive exists.

| Column | Type | Meaning |
|---|---|---|
| `rank` | int | Position 1-50 |
| `id` | str | Apple Music song id |
| `name` | str | Song name |
| `artist_name` | str | Performing artist(s) |
| `composer_name` | str | Composer(s) (often empty) |
| `release_date` | date | Track release date |
| `duration_ms` | int | Duration (often empty) |
| `apple_music_url` | str | Apple Music URL |
| `artwork_url` | str | Cover art URL |
| `region` | str | Region code (`cn` or `us`) |
| `country` | str | Country name from Apple |
| `feed_updated` | date | When Apple updated this RSS |
| `fetched_at` | date | When we collected it |

---

## D. Raw Spotify / Wikipedia / Billboard China

These sources were explored but ultimately **removed** from the
final repo. See `docs/CROSS_PLATFORM_NOTES.md` for the full
rejection matrix.

---

## E. Processed (interim) CSVs

### `data/interim/qq_raw_long.csv`

Full concatenation of all `qq_topId{N}_weekly_long.csv` files.
~137 000 rows. Same schema as the per-topId long CSVs.

### `data/interim/song_year_by_topid.csv`

One row per `(top_id, top_title, song_id, year)` with:

| Column | Meaning |
|---|---|
| `weeks_on_chart` | Distinct weekly issues the song appeared in, this year, this chart |
| `peak_rank` | Best rank achieved (lower = better) |
| `mean_rank` | Average rank across appearances |
| `genres` | Comma-separated genre tags from chart membership |

### `data/interim/song_year_all.csv`

Same as above but aggregated across topIds (one row per
`(year, song_id)`):

| Column | Meaning |
|---|---|
| `top_ids_present` | How many of the seven QQ toplists the song appeared on |
| `weeks_total` | Total weekly issues across all topIds |
| `peak_rank_min` | Best rank across all topIds |
| `mean_rank_avg` | Weighted average rank across all topIds |
| `genres` | Comma-separated (deduplicated) genre tags |

### `data/interim/song_year_canonical.csv`

Canonical-version rows: `(canonical_key, singer, year)` reduced to
the highest-weeks version of each.

| Column | Meaning |
|---|---|
| `canonical_key` | Title stripped of (live / cover / remix / acoustic) markers |
| `weeks_total` | weeks_total of the chosen canonical version |
| `peak_rank_min` | peak_rank_min of the chosen canonical version |

### `data/interim/year_top5_most_average.csv`

Per year, top 5 songs closest to the year-centroid (Euclidean
distance in `(log_weeks, inv_peak)` space).

### `data/interim/year_top5_most_outlier.csv`

Per year, top 5 songs farthest from the year-centroid (Euclidean
distance).

### `data/interim/year_top5_most_outlier_lof.csv`

Per year, top 5 songs by **LOF** (Local Outlier Factor) within
the year. Distinct from Euclidean: LOF captures local anomalies
not just global distance.

### `data/interim/changepoints.csv`

Years where the QQ yearly trend has a statistically significant
changepoint.

### `data/interim/inter_topid_correlation.csv`

`Var1, Var2, cor` — pairwise correlations of yearly mean
log-weeks-on-chart across the seven QQ toplists.

### `data/interim/cross_region_patterns.csv`

Per-platform structural metrics from `R/17_cross_region_patterns.R`.

| Column | Meaning |
|---|---|
| `platform` | Platform name |
| `n_top` | Number of songs in the snapshot |
| `n_with_year` | Number of songs with non-NA `year` |
| `share_old_pre2018` | % of top-N released 2018 or earlier |
| `artist_gini` | Gini coefficient on per-artist rank counts |
| `top3_artist_share_pct` | % of top-N from the 3 most-frequent artists |

### `data/interim/top_in_each_genre.csv`

Top 5 most-week-total songs per inferred genre (rap / edm / guofeng).

### `data/interim/lof_vs_euclidean_overlap.csv`

`year, both, lof_only, euc_only` — agreement between LOF and
Euclidean outlier rankings, per year.

### `data/interim/wikipedia_chinese_music_events_by_year.csv`

Keyword hits in the Wikipedia `<year>_in_Chinese_music` articles
against a curated event vocabulary (Douyin / COVID / guofeng /
rap / edm / short_loop / boom).

---

## F. Random seed

All scripts that produce figures or rankings use
`set.seed(20251002)` so that re-running the pipeline yields
identical numeric results.