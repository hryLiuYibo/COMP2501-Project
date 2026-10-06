# 02_yearly_summary.R
# (Originally named 02_pca.R; renamed because no PCA is performed
# in this script -- only per-year aggregate summary + line plots.)
#
# Build a song-year feature matrix from chart history metadata only.
# This is the "no-audio-yet" baseline: feature = profile of when/how a
# song was popular. Once we get audio embeddings, the same scaffolding
# can plug them in.
#
# Features (per song-year row):
#   - peak_rank (lower = better hit)
#   - weeks_on_chart
#   - weeks_top10, weeks_top20
#   - year (so we can colour by year)
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(ggplot2)
  library(scales)
})

ROOT <- normalizePath(".")
song_year_all <- read_csv(file.path(ROOT, "data", "interim",
                                    "song_year_all.csv"),
                           show_col_types = FALSE)

# build the matrix
mat <- song_year_all %>%
  filter(!is.na(year)) %>%
  group_by(year, song_id) %>%
  summarise(
    title = first(song_title),
    singer = first(singer_name),
    album = first(album_mid),
    weeks_total = sum(weeks_total, na.rm = TRUE),
    peak_rank = min(peak_rank_min, na.rm = TRUE),
    top_ids = n_distinct(top_ids_present),
    .groups = "drop"
  ) %>%
  mutate(
    log_weeks = log1p(weeks_total),
    inv_peak_rank = log1p(101 - pmin(peak_rank, 100))
  )

# year-by-feature table (one row per year, value = mean across that year)
feat_by_year <- mat %>%
  group_by(year) %>%
  summarise(
    n_songs = n(),
    avg_weeks = mean(weeks_total),
    avg_peak = mean(peak_rank),
    .groups = "drop"
  )

p1 <- ggplot(feat_by_year, aes(year, avg_weeks)) +
  geom_line(colour = "#3964fe", linewidth = 1) +
  geom_point(colour = "#3964fe") +
  scale_y_continuous(labels = comma) +
  labs(title = "Mean weeks-on-chart per song, by year",
       x = "Year", y = "Avg weeks on QQ Hot Songs + Online Songs") +
  theme_minimal()
ggsave(file.path(ROOT, "data/interim/year_avg_weeks.png"),
       p1, width = 7, height = 4, dpi = 110)

p2 <- ggplot(feat_by_year, aes(year, avg_peak)) +
  geom_line(colour = "#fc7e2f", linewidth = 1) +
  geom_point(colour = "#fc7e2f") +
  labs(title = "Mean peak rank per song (lower = bigger hit), by year",
       x = "Year", y = "Avg peak rank (1 = #1)") +
  theme_minimal()
ggsave(file.path(ROOT, "data/interim/year_avg_peak.png"),
       p2, width = 7, height = 4, dpi = 110)

cat("Wrote data/interim/year_avg_weeks.png, year_avg_peak.png\n")
cat("feature table:\n"); print(feat_by_year, n = Inf)