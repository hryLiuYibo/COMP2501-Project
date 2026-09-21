# R — data pipeline

The entire project runs in R. Python is **not** used anywhere — the design
decision to commit to 100 % R is recorded in [`../DESIGN.md`](../DESIGN.md)
and the course context (COMP2501 is taught around R).

This directory contains the **engineering** layer of the project. The
analysis notebooks live in [`analysis/`](./analysis/).

## Pipeline at a glance

```
[1] fetch_weekly_top100.R    →  data/raw/weekly_top100/<YYYY-Www>.json
[2] (external) download .ncm →  data/ncm/<song_id>.ncm
[3] convert_ncm_to_mp3.R     →  data/mp3/<song_id>.mp3     (CLI backend)
[4] extract_audio_features.R →  data/embeddings/song_features.csv
[5] analysis/*.Rmd           →  01_eda, 02_dim_reduce, 03_drift, ...
```

Only `song_features.csv` and `song_features_failures.csv` are committed
from `data/embeddings/`. Everything else under `data/` is `.gitignore`-d.

## Scripts

| Script | Role | Status |
| --- | --- | --- |
| `fetch_weekly_top100.R` | Hit NetEase toplist page, parse embedded JSON, dump to disk | Works |
| `convert_ncm_to_mp3.R`   | Wrap a CLI tool to decrypt `.ncm` into `.mp3`            | Works (CLI backend required) |
| `extract_audio_features.R`| Read each `mp3` with `tuneR`, compute MFCC / spec / chroma / tempo / ZCR | Works |
| `analysis/01_eda.Rmd`            | Descriptive stats, persistent songs, rank entropy | Skeleton |
| `analysis/02_dimension_reduction.Rmd` | PCA + UMAP of the feature matrix            | Skeleton |
| `analysis/03_temporal_drift.Rmd`      | Yearly centroid + drift time series           | Skeleton |

## R packages used

Already required:

- `httr`         — HTTP client (toplist fetch)
- `jsonlite`     — JSON parse / emit
- `rvest`        — HTML parsing (currently we drop straight to JSON, but it's a useful fallback)
- `tidyverse`    — analysis layer
- `dplyr`, `readr`, `tibble`, `purrr`  — via tidyverse

Audio:

- `tuneR`        — mp3 / wav decoding
- `seewave`      — MFCC, spectral descriptors, chroma, tempo, ZCR

Optional analysis packages (install when first needed):

- `uwot`         — UMAP
- `factoextra`   — prettier PCA / clustering plots
- `lubridate`    — week arithmetic

## Running the pipeline

### 1. Fetch one toplist snapshot

```bash
Rscript R/fetch_weekly_top100.R --week auto --top 100 --out data/raw/weekly_top100
Rscript R/fetch_weekly_top100.R --week 2025-W38 --top 200 --out data/raw/weekly_top100
```

`--week auto` picks the current ISO week (Mon-based).
The script supports `--top 1..200`. The toplist page currently returns up
to 200 songs; older descriptions of "Top 100" only reflect what NetEase
used to publish.

### 2. Decrypt ncm → mp3

```bash
# using ncmdump.exe (recommended; fastest)
Rscript R/convert_ncm_to_mp3.R --src data/ncm --dst data/mp3 --backend ncmdump --exe path/to/ncmdump.exe

# using ncmdump-py (Python wrapper, no separate binary needed)
Rscript R/convert_ncm_to_mp3.R --src data/ncm --dst data/mp3 --backend ncmdump-py
```

Resumable: mp3s that already exist are skipped.

### 3. Extract features

```bash
Rscript R/extract_audio_features.R \
    --src data/mp3 \
    --catalog data/songs_catalog.json \
    --out data/embeddings
```

Produces `song_features.csv` (committed) and `song_features_failures.csv`
(committed — this is the audit log of songs we couldn't process).

## About the toplist snapshot

NetEase does **not** publish a historical archive of the hot-song chart. The
toplist page shows the live chart at the moment you query. To produce a
5-year series we re-query on different days and store each result under
the ISO week of the query date. This is documented in
[`../DESIGN.md`](../DESIGN.md#33-snapshot-vs-actual-week).

## Legal note

`.ncm` is decrypted locally and the resulting `.mp3` is processed for
features only. **No audio is committed to the repo or redistributed.**
See `../DESIGN.md` §12 for the full legal / compliance table.
