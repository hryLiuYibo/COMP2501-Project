# 14_lof_outliers.R
# Replace Euclidean-distance-based outlier detection with LOF
# (Local Outlier Factor) for "most atypical song per year".
#
# Why LOF over plain Euclidean distance: LOF captures *local*
# anomalies. A 2019 song can be globally distant from the
# 2020 centroid but locally typical within 2019, or vice versa.
# Plain Euclidean misses this.
#
# Implementation: base R + dbscan::lof. dbscan::lof is shipped with
# the dbscan package, which we already use indirectly via HDBSCAN
# upstream. If dbscan is not installed, fall back to a custom LOF.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(ggplot2)
})

ROOT <- normalizePath(".")
song_year_all <- read_csv(file.path(ROOT, "data/interim/song_year_all.csv"),
                          show_col_types = FALSE) %>%
  filter(!is.na(year), year >= 2018)

# Build per-song feature vector: log-weeks, inv-peak, top_ids_present
fmat <- song_year_all %>%
  mutate(
    log_weeks = log1p(weeks_total),
    inv_peak  = 1 / log1p(peak_rank_min)
  )

# Try dbscan::lof; fall back to manual LOF if not available
use_dbscan <- requireNamespace("dbscan", quietly = TRUE)
cat("dbscan available:", use_dbscan, "\n")

if (use_dbscan) {
  dbscan::lof
  compute_lof <- function(X, k = 10) {
    as.numeric(dbscan::lof(X, k = k))
  }
} else {
  # Manual LOF: for each row, compute density of k-NN and ratio
  # to row's own density. Works fine for n<10K but slower.
  compute_lof <- function(X, k = 10) {
    n <- nrow(X)
    if (n <= k) return(rep(1, n))
    D <- as.matrix(dist(X))
    L <- numeric(n)
    for (i in seq_len(n)) {
      nn_idx <- order(D[i, ])[2:(k + 1)]   # exclude self
      reach_i <- D[i, nn_idx]
      # density_i = 1 / mean reach
      lrd_i <- 1 / (mean(reach_i) + 1e-9)
      # lrd of neighbours
      lrd_n <- numeric(k)
      for (j in seq_along(nn_idx)) {
        nn_j <- order(D[nn_idx[j], ])[2:(k + 1)]
        reach_ij <- max(D[nn_idx[j], nn_j], D[nn_idx[j], i])
        lrd_n[j] <- 1 / (mean(reach_ij) + 1e-9)
      }
      L[i] <- mean(lrd_n) / (lrd_i + 1e-9)
    }
    L
  }
}

# Compute LOF per year (so local-ness is intra-year)
lof_per_year <- fmat %>%
  group_by(year) %>%
  group_modify(~ {
    X <- as.matrix(.x[, c("log_weeks", "inv_peak", "top_ids_present")])
    .x$lof <- compute_lof(X, k = min(10, nrow(.x) - 1))
    .x
  }) %>%
  ungroup()

# Per-year "most outlier" songs by LOF
outlier_lof <- lof_per_year %>%
  group_by(year) %>%
  slice_max(order_by = lof, n = 5, with_ties = FALSE) %>%
  ungroup() %>%
  select(year, song_id, song_title, singer_name,
         weeks_total, peak_rank_min, top_ids_present, lof)

cat("\n=== Per-year most-outlier songs by LOF ===\n")
print(outlier_lof, max = 60)

write_csv(outlier_lof,
          file.path(ROOT, "data/interim/year_top5_most_outlier_lof.csv"))

# Also keep Euclidean-distance version for comparison
mat <- fmat
centroid_per_year <- mat %>%
  group_by(year) %>%
  summarise(
    cx = mean(log_weeks, na.rm = TRUE),
    cy = mean(inv_peak, na.rm = TRUE),
    .groups = "drop"
  )
dist_to_centroid <- function(df, cdf) {
  out <- df %>%
    inner_join(cdf, by = "year") %>%
    mutate(d = sqrt((log_weeks - cx)^2 + (inv_peak - cy)^2))
  out
}
dist_df <- dist_to_centroid(mat, centroid_per_year)
outlier_euc <- dist_df %>%
  group_by(year) %>%
  slice_max(order_by = d, n = 5, with_ties = FALSE) %>%
  ungroup() %>%
  select(year, song_id, song_title, singer_name,
         peak_rank_min, d)

# Agreement: do LOF and Euclidean pick the same songs?
overlap_check <- outlier_lof %>%
  select(year, song_id) %>%
  mutate(in_lof = TRUE) %>%
  full_join(outlier_euc %>% select(year, song_id) %>%
              mutate(in_euc = TRUE),
            by = c("year", "song_id")) %>%
  mutate(in_lof = !is.na(in_lof),
         in_euc = !is.na(in_euc)) %>%
  group_by(year) %>%
  summarise(
    both    = sum(in_lof & in_euc),
    lof_only = sum(in_lof & !in_euc),
    euc_only = sum(!in_lof & in_euc),
    .groups = "drop"
  )
cat("\n=== Overlap between LOF-top5 and Euclidean-top5 per year ===\n")
print(overlap_check, max = 30)

write_csv(overlap_check,
          file.path(ROOT, "data/interim/lof_vs_euclidean_overlap.csv"))