# Ten-Year Music Taste Drift — NetEase Edition

> COMP2501 Introduction to Data Science — Course Project

A data-science analysis of how Chinese music listeners' tastes have evolved over roughly the past five years, using the **NetEase Cloud Music** weekly hot-song chart as the data source. Each song is converted to a feature vector from its audio, and the resulting high-dimensional space is explored for yearly "average songs", "most distinctive songs", and overall drift.

---

## Highlights

- **Single platform, weekly snapshots** — NetEase Cloud Music `热歌榜`, top 100, weekly cadence, target range **2020–2025**.
- **Audio → vector** using a pretrained music-embedding model (Jukemir / MusicNN / CLAP under evaluation) — *no model is trained from scratch.*
- **Analysis stack** is R (`tidyverse`, `ggplot2`, plus clustering/PCA later in the course). Python is only used for scraping and audio preprocessing.
- **Local-only mp3 handling** — `.ncm` files are downloaded, converted to `.mp3` locally via the CLI tool [`ncmdump`](https://github.com/anonymous5l/ncmdump) (configured through `data-pipeline/convert_ncm_to_mp3.py`), used to extract features, then deleted. Nothing is redistributed. The repo no longer relies on a GUI drag-drop `.exe`.

---

## Repository layout

```
COMP2501-Project/
├── README.md                  # This file (English, public-facing)
├── Proj_Proposal_Firstidea.md # v1 idea brief, written in Chinese for the team
├── DESIGN.md                  # Pipeline + timeline + role split (Chinese, team-internal)
├── .gitignore
│
├── data-pipeline/             # Scraping + audio preprocessing (Python)
│   ├── fetch_weekly_top100.py # NetEase weekly top-100 scraper (main entry)
│   ├── README.md              # How to run the pipeline
│   └── (later) embed_audio.py # mp3 → feature vector
│
├── analysis/                  # Downstream analysis (R)
│   └── (R Markdown reports, scripts, plots go here)
│
├── data/                      # NOT committed (see .gitignore)
│   ├── raw/                   # weekly JSON snapshots, song metadata
│   ├── ncm/                   # downloaded .ncm files (temporary)
│   ├── mp3/                   # converted .mp3 files (temporary)
│   └── embeddings/            # Final song × vector matrix (committed, small)
│
└── docs/                      # Reports, slides, write-ups
```

---

## Tech stack

| Layer | Tool |
| --- | --- |
| Scraping | Python (preferred) or Node.js |
| Audio embedding | Python + pretrained model (Jukemir / MusicNN / CLAP) |
| Data analysis | R + `tidyverse` + `ggplot2` (course requirement) |
| Modeling (later) | R `tidymodels` / `caret` |
| Final report | R Markdown (course assignment format) |

Python and R are decoupled: Python emits a tidy CSV of `song_id × feature_vector`, R takes it from there.

---

## Data source

- **Platform**: NetEase Cloud Music (网易云音乐)
- **Chart**: 热歌榜 (weekly hot-song chart)
- **Snapshot frequency**: weekly
- **Songs per snapshot**: top 100
- **Time range**: 2020–2025 (≈ 5 years × 52 weeks ≈ 260 snapshots)
- **Storage deduplication**: a song appears in many weeks; unique-song count after dedup is much lower than 26,000

Historical snapshots are captured by polling the live chart retroactively. Since the chart itself is forward-scrolling, the snapshot for week N is captured at any later point by saving the rank list at the moment we query.

---

## Audio feature pipeline

```
[1] fetch_weekly_top100.py   →  data/raw/weekly_top100/YYYY-WW.json
[2] download_ncm.py          →  data/ncm/{song_id}.ncm
[3] convert_ncm_to_mp3.py    →  data/mp3/{song_id}.mp3   (CLI; ncmdump backend)
[4] embed_audio.py           →  data/embeddings/song_vectors.csv
[5] delete .mp3 (keep embeddings only)
```

Only `song_vectors.csv` is committed. Audio files never enter git.

---

## How to run (will be expanded)

```bash
# 1. Scrape weekly top-100 snapshots
python data-pipeline/fetch_weekly_top100.py \
    --start 2020-W01 --end 2025-W52 \
    --top 100 \
    --out data/raw/weekly_top100

# 2. Convert to audio features
python data-pipeline/embed_audio.py \
    --in data/mp3 \
    --out data/embeddings/song_vectors.csv
```

Detailed instructions live in `data-pipeline/README.md` (TBD).

---

## Course context

- **Course**: COMP2501 Introduction to Data Science, HKU SDS, taught by RB Luo
- **Project weight**: 30% of final grade
- **Format**: R Markdown report + 10–20 min presentation, 1 or 2 students
- **Submission deadlines**:
  - Proposal: 28–30 Sep 2026, 11:59 pm
  - Final presentation: TBA
- **AI policy**: Use of LLMs (including the assistant used to write this README) is permitted for learning and coding, but every line must be understood by the author. Do not submit LLM-generated text as assignment work.

See `Proj_Proposal_Firstidea.md` for the original idea brief (in Chinese, for team-internal use).

---

## Status

🚧 **Very early stage** — repository initialized, project scope agreed, scraping pipeline being designed.

---

## Team & language conventions

- Two collaborators on the GitHub repo
- Internal notes, design docs, code comments: **Chinese**
- GitHub commits, README, R Markdown reports, course-facing documents: **English**