# Proposal 4 & 5 (Data + Feature) — QQ Music Data Section

This is a drop-in block you can put in section 4 of your proposal.
It is honest about what was collected, what was not, and why.

---

## 4. Data Sources & Acquisition (final)

#### 4.1 Main Data Source: QQ Music public weekly toplists

For this project we use QQ Music's public weekly toplist endpoint
`https://u.y.qq.com/cgi-bin/musicu.fcg`, the same endpoint used by
the QQ Music web client. The endpoint requires no login, no API key,
and no anti-bot handling.

```
POST https://u.y.qq.com/cgi-bin/musicu.fcg
Content-Type: application/json; charset=utf-8

{
  "comm":  {"ct": 24, "cv": 0},
  "detail": {
    "module": "musicToplist.ToplistInfoServer",
    "method": "GetDetail",
    "param": {
      "topId":   <int>,
      "offset":  0,
      "num":     100,
      "period":  "<YYYY_WNN>"     // e.g. "2020_30"
    }
  }
}
```

#### 4.1.1 Toplists used

Seven toplists are collected. Four belong to the "巅峰榜" (Peak /
Top) family; three are "风味榜" specialty genre-tagged charts which we
use as the source of inferred genre labels (Section 5.3).

| topId | Title          | Group    | Issues | Unique songs | Genre tag |
|------:|----------------|----------|-------:|-------------:|-----------|
|    26 | 热歌榜          | 巅峰榜   |    202 |       1942 | -          |
|    28 | 网络歌曲榜       | 特色榜   |    331 |       9626 | -          |
|     5 | 内地榜          | 地区榜   |    288 |      10928 | -          |
|    58 | 说唱榜          | 特色榜   |    195 |       3125 | rap        |
|    57 | 电音榜          | 特色榜   |    191 |        2878 | edm        |
|    65 | 国风热歌榜       | 特色榜   |    194 |        1303 | guofeng    |
|    60 | 抖音热歌榜       | 特色榜   |    167 |        1729 | -          |
| **total** | **—**     | **—**    | **—** | **~29 500** | |

Each toplist gives 50-200 chart entries per weekly issue. Total raw data
is approximately **137 thousand song-week rows**.

#### 4.1.2 Coverage: 2018 W30 – 2024 W52

The `period` parameter is silently honoured by the server only for
**2018 week 30 to 2024 week 52**. Outside this window the server
returns the current period (`2026-10-02` in our case). Earlier
toplist data (2015–2017) and 2025+ are not recoverable through any
endpoint we have found on QQ Music.

The original proposal said "2015–2025". After probing we have
narrowed the actual analysis window to "2018–2024 (7 years)" and we
treat this as our "scope of analysis" in the rest of the report.

#### 4.2 Metadata fields

For each `(topId, period, rank)` triple we record:

```
top_id, top_title, period, rank, song_id, song_mid,
song_title, singer_name, singer_mid, album_mid, cover,
song_type, rank_value, rank_type,
genre_inferred, chart_listen_num, chart_update_time, fetched_at
```

#### 4.2.1 Fields NOT available

QQ Music's per-song detail endpoint (e.g. `music.pf_song_detail_svr`)
returns `code=500003` ("fail: missing param/sig") without a logged-in
session since 2024. The following per-song fields therefore cannot be
collected from the public API at the time of writing:

- Per-song play count
- Comment count / lyrics / song length / language
- Direct genre / label / language tags

We do **not** acquire per-song play count from any third party; this is
a scope limit documented in Section 4.4.

#### 4.3 Version normalization

QQ does not expose a clean version flag. We do version
normalisation through a two-step regex on `song_title`:

1. **Flag detection**: each song-year row is tagged
   `is_live`, `is_cover`, `is_remix`, `is_draft` based on whether
   the title contains any of:

   | flag    | regex (case-insensitive) |
   |---------|-------------------------|
   | live    | `live` / `现场` / `现场版` / `演唱会版` / `纯享版` |
   | cover   | `cover` / `翻唱` / `翻自` / `致敬版` |
   | remix   | `remix` / `混音` / `extended` / `dj remix` / `mashup` / `remaster` |
   | draft   | `demo` / `练习室` / `acoustic` / `unplugged` / `钢琴版` / `伴奏` / `纯人声` |

2. **Canonical dedup**: strip `(...)` / `（...)` brackets and the
   markers above; the result is `canonical_key`. Within each
   `(canonical_key, singer, year)`, keep only the song having the
   highest total weeks-on-chart across the seven toplists.

Output: `data/interim/song_year_canonical.csv` (one row per canonical
version per year per singer).

#### 4.4 Compliance

We follow a strict, narrow compliance boundary:

- **No audio download**. The mp3 is never fetched or stored on this
  project's filesystem at any time.
- **No transcript or lyric download**. Lyric endpoint requires
  per-song key derivation; we are not in this draft.
- **No third-party API**. We hit QQ Music's own `u.y.qq.com` endpoint
  with `Referer: https://y.qq.com/` header; no proxy, no mirror.
- **No login**. No QQ Music account cookie, no token. This is also
  why `code=500003` blocks us out of song-detail endpoints.

| operation                              | risk | note |
|----------------------------------------|------|------|
| Pull weekly toplist metadata           | low     | public endpoint, fair-use, ~30 unique songs in 7 years |
| Pull per-song detail                  | blocked | requires login as of 2024 (`code=500003`) |
| Download mp3                           | not done | out of scope per proposal 4.4 |
| Upload mp3                             | not done | out of scope per proposal 4.4 |
| Delete mp3 after feature extraction    | not done | we never had mp3 |

---

## 5. Feature Engineering (final)

#### 5.1 Chart-history features (this version)

Because per-song audio embeddings are out-of-scope per user request
(see Section 7), we restrict feature engineering to **chart-history
features only**. Each song-year row carries:

- `weeks_total` — total weeks the song showed up on any of the
  seven toplists in that year (sum across toplists).
- `peak_rank_min` — minimum rank (best position) on any of the seven
  toplists in that year.
- `top_ids_present` — how many of the seven toplists the song
  appeared on.
- `genres` — comma-separated genre tag(s) inferred via Section 5.3.

These features are sufficient to answer all three research questions
in Section 3 of the proposal at the chart-history level. We discuss
the direction in Section 7.

#### 5.2 Genre inference

Three genres are inferred for free from chart membership: a song that
appeared on the rap chart (topId=58) at least once in a year is
labelled `rap` for that year; ditto `edm` (topId=57) and `guofeng`
(topId=65). The remaining genres (ballad, pop, indie, etc.) are
out of scope per Section 4.2.1.

#### 5.3 Cover / live / remix / draft flags

See Section 4.3.

#### 5.4 Audio features (out of scope)

This draft does **not** include MERT, Jukemir, CLAP, or librosa-based
audio embeddings. These are explicitly out-of-scope per user request
and are discussed in Section 7.