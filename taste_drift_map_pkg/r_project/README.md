# Taste Drift Map — R figure pipeline

Every figure in the English deck (`docs/presentation_v3_en.pptx`, slides 17–28)
is produced by the R scripts in this folder, from the CSVs in `data/`.

## Reproduce

```r
# one-time
install.packages(c("ggplot2", "dplyr", "readr", "tidyr", "scales",
                   "patchwork", "ggrepel", "ragg"))
# then
Rscript run_all.R        # regenerates all 9 figures into ../figures/
```

R version used: 4.6.1 (Windows). Any R >= 4.2 should work.

Figures are written to the **repository root's** `figures/` (not this folder), so
that R output and the Python-generated figures live side by side and
`scripts/build_pptx_en.py` can pick them all up from one place.

## Pipeline

```
data/raw/audio + data/raw/charts
        |
        v  (Python, one-time: matching + CLAP vectorization + analysis)
   scripts/export_for_r.py  ---->  r_project/data/*.csv   (flat, utf-8-sig, R-ready)
        |
        v  (R, all plotting + statistics)
   r_project/run_all.R  ---->  figures/*.png  ---->  scripts/build_pptx_en.py assembles the deck
```

- **Python side** (`scripts/export_for_r.py`): CLAP embeddings, chart-audio
  matching, and signal processing (STFT / Mel filterbank / waveform envelope).
  It exports *numbers only*.
- **R side** (this folder): all plotting AND all statistics that matter for the
  course (platform centroids, same-year angles, single-song AUC + 2000-fold
  bootstrap, centroid-shift bootstrap, coverage rates).

## Data dictionary (`data/`)

| file | rows | what it is |
|---|---|---|
| `songs.csv` | 489 | one row per chart entry that matched local audio: platform, year, month, rank, title, artist, file, normalized title, overlap class |
| `songs_unique.csv` | 374 | one row per unique audio file |
| `vectors.csv` | 489 | PCA coordinates (PC1-PC3) of each chart entry |
| `song_vectors_512.csv` | 374 | the raw 512-dim CLAP vectors (unit norm) - input for the R bootstrap |
| `centroid_pc.csv` | 14 | yearly centroids per platform in PCA space (+ n songs) |
| `monthly_pc.csv` | 75 | monthly centroids (QQ) / yearly (NetEase) in PCA space |
| `metrics_q1.csv` | 13 | platform-difference metrics (long format) |
| `margins.csv` | 374 | per-song margin = cos(song, QQ centroid) - cos(song, NE centroid); one row per platform x song (319 QQ + 55 NE, chart repeats not double-counted) - input for the AUC bootstrap |
| `drift_annual.csv` | 12 | adjacent-year centroid drift per platform |
| `monthly_drift.csv` | 75 | angle of each month's centroid to 2018-08 (QQ) |
| `year_structure.csv` | 12 | within-year dispersion + Chinese-title share |
| `coverage.csv` | 14 | chart entries matched to local audio, per year/platform |
| `coverage_summary.csv` | 2 | overall hit rates |
| `pairwise_cosine.csv` | 74305 | all C(386,2) pairwise cosines of the library |
| `probe_meta.csv` | 1 | the sample song: Snow Distance, 166 s, 17 windows |
| `probe_waveform.csv` | 2700 | min/max envelope of the full waveform |
| `probe_stft.csv` | 40014 | linear STFT of window 3 (long format) |
| `probe_mel.csv` | 14976 | 64-band log-Mel spectrogram of window 3 (long format) |
| `probe_windows.csv` | 17 | the 17 window embeddings (512 dims each) |
| `probe_chain.csv` | 289 | 17x17 window-to-window cosine matrix (long) |
| `probe_similarity.csv` | 386 | cosine of the sample song to every library song |

## Scripts

| script | figure | content |
|---|---|---|
| `theme_taste.R` | - | shared ggplot theme, palette (QQ = red #DC2626, NetEase = blue #2563EB) |
| `01_map_overview.R` | map_overview.png | all songs in PC1/PC2 + overlap bars |
| `02_map_platform.R` | map_platform.png | same-year centroid angles (computed in R) + AUC bootstrap (2000 resamples, computed in R) |
| `03_map_trajectory.R` | map_trajectory.png | yearly centroid trajectory + drift vs bootstrap shift (300 resamples/year, computed in R) |
| `04_map_monthly.R` | map_monthly.png | monthly centroid angles, 66 months |
| `05_map_coverage.R` | map_coverage.png | audio coverage per year |
| `06_chain_waveform.R` | chain_1_waveform.png | waveform + 10 s windowing |
| `07_chain_spectrogram.R` | chain_2_spectrogram.png | STFT vs log-Mel (window 3) |
| `08_chain_vector.R` | chain_3_vector.png | 17x512 heatmap + top dims + window cosine |
| `09_chain_similarity.R` | chain_4_similarity.png | cosine histogram, narrow cone |

Key numbers produced by R (also written to `auc_bootstrap.txt` /
`bootstrap_noise.txt` and quoted on the deck): AUC = 0.661, 95% CI
[0.591, 0.732]; full-period centroid angle 3.93 degrees; bootstrap centroid
shift 2.6-4.3 degrees/year.
