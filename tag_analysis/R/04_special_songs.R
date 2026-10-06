# 04_special_songs.R
# For each year: pick the "most average" song (closest to annual centroid
# in feature space) and the "most atypical" song (farthest from it).
# Uses chart-history features only (audio features slot in later).
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
})

ROOT <- normalizePath(".")
mat <- read_csv(file.path(ROOT, "data/interim/song_year_all.csv"),
                show_col_types = FALSE) %>%
  filter(!is.na(year)) %>%
  mutate(
    log_weeks = log1p(weeks_total),
    inv_peak = 1 / log1p(peak_rank_min)
  )

centroid_per_year <- mat %>%
  group_by(year) %>%
  summarise(
    cx = mean(log_weeks, na.rm = TRUE),
    cy = mean(inv_peak,  na.rm = TRUE),
    .groups = "drop"
  )

dist_to_centroid <- function(df, cdf) {
  out <- df %>%
    inner_join(cdf, by = "year") %>%
    mutate(d = sqrt((log_weeks - cx)^2 + (inv_peak - cy)^2))
  out
}

dist_df <- dist_to_centroid(mat, centroid_per_year)

avg_per_year <- dist_df %>%
  arrange(year, d) %>%
  group_by(year) %>% slice_head(n = 5) %>% ungroup()
outlier_per_year <- dist_df %>%
  arrange(year, desc(d)) %>%
  group_by(year) %>% slice_head(n = 5) %>% ungroup()

write_csv(avg_per_year,
          file.path(ROOT, "data/interim/year_top5_most_average.csv"))
write_csv(outlier_per_year,
          file.path(ROOT, "data/interim/year_top5_most_outlier.csv"))

cat("\n=== Most average song per year (top 5/yr) ===\n")
print(avg_per_year %>%
        select(year, song_title, singer_name, weeks_total, peak_rank_min, d) %>%
        as.data.frame(), max = 100)

cat("\n=== Most outlier song per year (top 5/yr) ===\n")
print(outlier_per_year %>%
        select(year, song_title, singer_name, weeks_total, peak_rank_min, d) %>%
        as.data.frame(), max = 100)