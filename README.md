# Five-Year Music Taste Drift — NetEase Edition

> COMP2501 Introduction to Data Science — Course Project

A data-science analysis of how Chinese music listeners' tastes have evolved
over roughly the past five years, using the **NetEase Cloud Music** weekly
hot-song chart as the data source. Each song is converted to a feature
vector from its audio, and the resulting high-dimensional space is explored
for yearly "average songs", "most distinctive songs", and overall drift.

[中文版 / Chinese version](./README.zh.md)

---

## Highlights

- **Single platform, weekly snapshots** — NetEase Cloud Music `热歌榜`, weekly cadence, target range **2020–2025**.
- **Single-language stack — R only.** Python is *not* used anywhere in the project. The decision to stay in 100% R is recorded in [`DESIGN.md`](DESIGN.md). Course context (COMP2501) is taught around R, and we want to be unambiguous about not introducing a second language.
- **Audio → vector** using classical MIR descriptors (`tuneR::melfcc` for MFCCs, custom FFT-based spectral descriptors, a 12-bin chroma implementation, plus tempo and ZCR from `seewave`). No Python, no PyTorch.
- **Local-only mp3 handling** — `.ncm` files are downloaded, converted to `.mp3` locally via the CLI tool [`ncmdump`](https://github.com/taurusxin/ncmdump) (called from R via `system2`), used to extract features, then deleted. Nothing is redistributed.

---

## Repository layout

```
COMP2501-Project/
├── README.md                   # English default
├── README.en.md                # English (same content as README.md)
├── README.zh.md                # Chinese version
├── TODO.md                     # Next-step checklist (Chinese, team-internal)
├── Proj_Proposal_Firstidea.md  # v1 idea brief (Chinese, team-internal)
├── DESIGN.md                   # Pipeline + timeline + pitfalls (Chinese)
├── .gitignore
│
├── R/                          # R data pipeline + analysis notebooks
│   ├── README.md               # How to run the R scripts
│   ├── fetch_weekly_top100.R   # [1] Scrape weekly toplist via rvest + httr
│   ├── convert_ncm_to_mp3.R    # [2] ncm → mp3 via CLI (ncmdump)
│   ├── build_songs_catalog.R   # [3] Generate catalog from mp3 dir
│   ├── extract_audio_features.R# [4] mp3 → classical audio features
│   └── analysis/               # [5] R Markdown reports (EDA, dim. reduction, drift)
│
├── data/                       # NOT committed (see .gitignore)
│   ├── raw/weekly_top100/      # weekly JSON snapshots (gitignored)
│   ├── ncm/                    # downloaded .ncm files (temporary, gitignored)
│   ├── mp3/                    # converted .mp3 files (temporary, gitignored)
│   ├── embeddings/             # song_features.csv (committed)
│   └── songs_catalog.json      # song index (committed)
│
└── docs/                       # Reports, slides, write-ups
```

---

## Tech stack

| Layer | Tool |
| --- | --- |
| Web scraping | R + `httr` + `rvest` + `jsonlite` |
| ncm → mp3 | R → `shell("ncmdump.exe")` (no in-R decoder) |
| Audio decoding | R + `tuneR::readMP3()` |
| Audio features | R + `tuneR::melfcc()`, custom FFT helpers, `seewave::timer/zcr` |
| Data analysis | R + `tidyverse` + `ggplot2` |
| Dim. reduction | R + base `prcomp` + `uwot::umap` |
| Final report | R Markdown |

The single-language stack means there is **no Python → R boundary**: each
script writes outputs that the next script reads, all within R.

---

## Data source

- **Platform**: NetEase Cloud Music (网易云音乐)
- **Chart**: 热歌榜 (weekly hot-song chart)
- **Source strategy**: the public toplist page is server-side rendered; the top ~200 songs are embedded as a JSON array inside a `<textarea id="song-list-pre-data">` node. We do **not** call NetEase's signed JSON APIs (fragile, legally grey); we just `httr::GET()` the page and decode the JSON.
- **Snapshot frequency**: weekly
- **Songs per snapshot**: top 100 (page actually returns up to 200; we cap at 100)
- **Time range**: 2020–2025 (≈ 5 years × 52 weeks ≈ 260 snapshots)
- **Storage deduplication**: a song appears in many weeks; unique-song count after dedup is much lower than 26,000

Historical snapshots are captured by polling the live chart retroactively.
Since the chart itself is forward-scrolling, the snapshot for week N is
captured at any later point by saving the rank list at the moment we query.
The `week` label in each snapshot is the ISO week of the query, **not** a
NetEase-published "chart week" — NetEase does not publish weekly archives.

---

## Audio feature pipeline

```
[1] R/fetch_weekly_top100.R    →  data/raw/weekly_top100/<YYYY-Www>.json
[2] (external) download .ncm   →  data/ncm/<song_id>.ncm
[3] R/convert_ncm_to_mp3.R     →  data/mp3/<song_id>.mp3        (CLI: ncmdump)
[4] R/build_songs_catalog.R    →  data/songs_catalog.json
[5] R/extract_audio_features.R →  data/embeddings/song_features.csv
[6] delete .mp3 + .ncm (keep song_features.csv only)
```

`data/embeddings/song_features.csv` is the **only** committed artifact
under `data/`. Audio files in any format never enter git.

The 30-dim per-song feature vector is:

```
mfcc_1, ..., mfcc_13,
spec_centroid, spec_bandwidth, spec_flatness,
C, C#, D, D#, E, F, F#, G, G#, A, A#, B,   (chroma, 12-dim, sums to 1)
tempo, zcr
```

---

## How to run

```bash
# 1. One weekly snapshot (current ISO week)
Rscript R/fetch_weekly_top100.R --week auto --top 100 --out data/raw/weekly_top100

# 2. Decrypt ncm → mp3 (requires ncmdump.exe somewhere on disk)
Rscript R/convert_ncm_to_mp3.R \
    --src data/ncm --dst data/mp3 \
    --backend ncmdump --exe path/to/ncmdump.exe

# 3. Build catalog from mp3 directory
Rscript R/build_songs_catalog.R --mp3-dir data/mp3 --out data/songs_catalog.json

# 4. Extract features per song
Rscript R/extract_audio_features.R \
    --src data/mp3 --catalog data/songs_catalog.json --out data/embeddings

# 5. Open analysis notebooks
#    R/analysis/01_eda.Rmd, 02_dimension_reduction.Rmd, 03_temporal_drift.Rmd
```

Detailed instructions live in [`R/README.md`](R/README.md).

---

## Course context

- **Course**: COMP2501 Introduction to Data Science, HKU SDS
- **Project weight**: 30% of final grade
- **Format**: R Markdown report + 10–20 min presentation, 1 or 2 students
- **Submission deadlines**:
  - Proposal: 28–30 Sep 2026, 11:59 pm
  - Final presentation: TBA
- **AI policy**: Use of LLMs (including the assistant used to write this README) is permitted for learning and coding, but every line must be understood by the author. Do not submit LLM-generated text as assignment work.

See `Proj_Proposal_Firstidea.md` for the original idea brief (Chinese, team-internal), `DESIGN.md` for the full design document (Chinese), and `TODO.md` for the next-step checklist (Chinese).

---

## Status

🚧 **Pipeline plumbing is wired end-to-end on a 3-song fixture.**

- ✅ `R/fetch_weekly_top100.R` tested against live NetEase toplist (HTTP 200, 100 songs parsed, `song_id` precision preserved).
- ✅ `R/convert_ncm_to_mp3.R` ready (verified with `ncmdump.exe 1.5.0` on 3 real songs including Chinese filenames).
- ✅ `R/build_songs_catalog.R` ready.
- ✅ `R/extract_audio_features.R` ready (smoke-tested on 3 real songs).
- 🚧 `R/analysis/*.Rmd` are skeleton notebooks to be filled once 5-year data is wired through.

---

## Team & language conventions

- Two collaborators on the GitHub repo
- Internal notes, design docs, code comments, TODO: **Chinese**
- GitHub commits, README, R Markdown reports, course-facing documents: **English**
- The README is provided in both English (`README.md` / `README.en.md`) and Chinese (`README.zh.md`); GitHub auto-detects the language variant and shows a switcher.
