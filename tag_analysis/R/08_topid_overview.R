# 08_topid_overview.R
# 7-topId cross-trajectory + inter-topId correlation matrix.
# Adds cross-chart hot-vs-online alignment with all available charts.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(ggplot2)
})

ROOT <- normalizePath(".")
raw <- read_csv(file.path(ROOT, "data/interim/qq_raw_long.csv"),
                show_col_types = FALSE) %>%
  filter(!is.na(year))

# per topId x year summary
year_mean <- raw %>%
  group_by(top_id, top_title, year) %>%
  summarise(
    n_songs = n_distinct(song_id),
    avg_weeks = mean(n_distinct(period), na.rm = TRUE),
    .groups = "drop"
  )

# not directly comparable across charts; show n_songs instead
p <- ggplot(raw %>%
             count(top_title, year, name = "song_year_rows"),
           aes(year, song_year_rows, colour = top_title)) +
  geom_line(linewidth = 1) + geom_point(size = 1.6) +
  labs(title = "Yearly song-rows pulled, by QQ chart",
       x = "Year", y = "Song-year rows in raw data", colour = "Chart") +
  theme_minimal() +
  theme(legend.position = "right")
ggsave(file.path(ROOT, "data/interim/topid_overview.png"),
        p, width = 9, height = 5, dpi = 110)

# Inter-chart log_weeks correlation
weeks_per_song <- raw %>%
  group_by(top_id, top_title, year, song_id) %>%
  summarise(weeks = n_distinct(period), .groups = "drop") %>%
  group_by(top_id, top_title, year) %>%
  summarise(m_log_weeks = mean(log1p(weeks)), .groups = "drop")

aligned <- weeks_per_song %>%
  pivot_wider(id_cols = year, names_from = top_title,
              values_from = m_log_weeks)

corr_mat <- cor(aligned[,-1, drop=FALSE], use = "pairwise.complete.obs")
cat("Cross-chart correlation of yearly mean log(1+weeks):\n")
print(round(corr_mat, 2))

# write the corr matrix to CSV
write_csv(as.data.frame.table(corr_mat, responseName = "cor"),
          file.path(ROOT, "data/interim/inter_topid_correlation.csv"))
cat("Wrote data/interim/inter_topid_correlation.csv\n")
cat("Wrote data/interim/topid_overview.png\n")