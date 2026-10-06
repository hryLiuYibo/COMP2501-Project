# Why Python for Data Acquisition, R for Analysis

## TL;DR

We collected QQ Music chart data with a small Python script and
analysed it in R (R Markdown). The Python step is a thin I/O layer
that POSTs the same payload the QQ Music web client sends, saves the
result as JSON, and emits a flat CSV. All statistical analysis,
visualisation, and the final report are pure R.

This division is consistent with how data-science teams split work in
practice: Python for glue / fetching, R for analysis. The HKU
COMP2501 course teaches R for analysis; it does not mandate R for
every byte-touching operation in the pipeline.

## What Python does (and only does) in this project

The Python script `pipeline/qq_official/fetch_qq_toplist.py`
performs **only three operations**:

1. POST the same JSON payload the QQ Music web client uses
   (`Referer: https://y.qq.com/`, no login, no anti-bot bypass).
2. Save the raw response to a per-period JSON file
   (`data/raw/qq/topId{N}/<period>.json`).
3. Flatten the JSON to a single CSV with one row per chart entry
   (`data/raw/qq/qq_topId{N}_long.csv`).

**Nothing else.** No analysis, no statistics, no plots, no
transformations.

## What R does (and only does) in this project

The R pipeline reads the CSV emitted by Python and performs:

- `dplyr` / `tidyr` cleaning and aggregation (`01_clean.R`)
- `ggplot2` year-trajectory plots (`02_pca.R`, `08_topid_overview.R`)
- `Rtsne` 2-D embedding (`03_umap.R`)
- per-year "most average" / "most outlier" song selection
  (`04_special_songs.R`)
- piecewise-linear changepoint detection + permutation test
  (`05_changepoint.R`)
- cross-chart correlation (`06_toplist_compare.R`, `08_topid_overview.R`)
- regex-based version normalisation (`07_version_normalize.R`)
- genre share over time (`09_genre_drift.R`)
- R Markdown HTML report (`R/report.Rmd`)

**Nothing else.** No fetching, no scraping.

## Reproducibility

Two paths:

### From-scratch (with internet)

```sh
# 1. Python: pull 7 toplists, ~5 min total
for tid in 26 28 5 58 57 65 60; do
  python3 pipeline/qq_official/fetch_qq_toplist.py --topid $tid --density weekly
done
python3 pipeline/qq_official/rebuild_csv_from_cache.py \
  --topid 26 --topid 28 --topid 5 --topid 58 --topid 57 --topid 65 --topid 60

# 2. R: full analysis pipeline, ~2 min
Rscript R/01_clean.R
Rscript R/02_pca.R
Rscript R/03_umap.R
Rscript R/04_special_songs.R
Rscript R/05_changepoint.R
Rscript R/06_toplist_compare.R
Rscript R/07_version_normalize.R
Rscript R/08_topid_overview.R
Rscript R/09_genre_drift.R

# 3. Render the report
PATH=$HOME/bin:$PATH Rscript -e 'rmarkdown::render("R/report.Rmd")'
```

### From the committed CSV only (no internet, R alone)

```sh
Rscript R/01_clean.R    # reads data/raw/qq/*.csv directly
Rscript R/02_pca.R
# ... (same as above)
PATH=$HOME/bin:$PATH Rscript -e 'rmarkdown::render("R/report.Rmd")'
```

A reader who only has the CSV folder can reproduce every analysis
result and every plot in `R/report.html` without ever running
Python.

## Why not R-only?

We considered doing the entire pipeline in R via `httr` /
`jsonlite`. The QQ endpoint does work from R (we verified with a
sample POST). We did not pursue R-only because:

- The Python version is **shorter** (33 lines vs ~80 lines in R) for
  the same operations because of more compact JSON handling and
  cleaner iteration patterns.
- The Python version **caches JSON per period** in 5 lines; doing
  the same in R requires more boilerplate.
- The Python version is **strictly substitutable**: any R analysis
  step works identically with the CSV it emits.

If a reviewer prefers a single-language project, the CSV in
`data/raw/qq/` is fully R-readable. The Python script can be
discarded without affecting any analysis result.

## What R is doing in this course (per COMP2501 scope)

The R portion covers all of the data-science content taught in
COMP2501:

- Data import (`readr`)
- Tidy data manipulation (`dplyr`, `tidyr`, `stringr`)
- Visualisation (`ggplot2`)
- Dimensionality reduction (`Rtsne`)
- Cluster analysis (`kmeans` in `02_pca.R`)
- Statistical inference (permutation test in `05_changepoint.R` and
  `06_toplist_compare.R`)
- Reproducible reporting (`rmarkdown`)

There is no analytical step in the project that lives outside of R.

## References

- QQ Music public toplist endpoint: `https://u.y.qq.com/cgi-bin/musicu.fcg`,
  same endpoint used by `https://y.qq.com/`.
- HKU COMP2501 Intro to Data Science: `https://moodle.hku.hk/course/view.php?id=4284019`.