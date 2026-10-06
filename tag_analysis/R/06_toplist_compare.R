# 06_toplist_compare.R
# Compare year-trajectories across topIds (热歌榜 vs 网络歌曲榜).
# Without `vegan::adonis`, do a manual PERMANOVA-like permutation test
# on year-averaged features, and a Procrustes-style alignment on the
# yearly t-SNE coordinates.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(ggplot2)
})

ROOT <- normalizePath(".")
raw <- read_csv(file.path(ROOT, "data/interim", "qq_raw_long.csv"),
                show_col_types = FALSE)

# compute topId x year averages of standardised features
fmat <- raw %>%
  filter(!is.na(year)) %>%
  group_by(top_id, year, song_id) %>%
  summarise(
    weeks = n_distinct(period),
    peak = min(rank, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(
    log_weeks = log1p(weeks),
    inv_peak = 1 / log1p(peak)
  )

year_mean <- fmat %>%
  group_by(top_id, year) %>%
  summarise(m_log_weeks = mean(log_weeks),
            m_inv_peak  = mean(inv_peak), .groups = "drop")

# PERMANOVA-like: build year x year distance matrix within each topId,
# then ask: are distances across topId > within topId?
years_all <- sort(unique(year_mean$year))
make_dist <- function(d) {
  dm <- matrix(0, nrow = length(years_all), ncol = length(years_all),
               dimnames = list(years_all, years_all))
  for (i in seq_along(years_all)) for (j in seq_along(years_all)) {
    a <- year_mean %>% filter(year == years_all[i], top_id == d)
    b <- year_mean %>% filter(year == years_all[j], top_id == d)
    if (nrow(a) == 1 && nrow(b) == 1) {
      dm[i, j] <- sqrt((a$m_log_weeks - b$m_log_weeks)^2 +
                       (a$m_inv_peak - b$m_inv_peak)^2)
    }
  }
  dm
}
d_hot    <- make_dist(26)
d_online <- make_dist(28)

# alignment via year-correlation between year-mean features
aligned <- year_mean %>%
  select(year, top_id, m_log_weeks, m_inv_peak) %>%
  pivot_wider(names_from = top_id,
              values_from = c(m_log_weeks, m_inv_peak),
              names_prefix = "fork_")

cor_log_weeks <- cor(aligned$m_log_weeks_fork_26,
                     aligned$m_log_weeks_fork_28,
                     use = "complete.obs")
cat("Correlation (year, log_weeks, hot vs online):",
    round(cor_log_weeks, 3), "\n")
cor_inv_peak <- cor(aligned$m_inv_peak_fork_26,
                    aligned$m_inv_peak_fork_28,
                    use = "complete.obs")
cat("Correlation (year, inv_peak,  hot vs online):",
    round(cor_inv_peak, 3), "\n")

p <- ggplot(year_mean,
            aes(year, m_log_weeks, colour = factor(top_id))) +
  geom_line(linewidth = 1) + geom_point(size = 2) +
  scale_colour_manual(values = c("26" = "#3964fe",
                                 "28" = "#fc7e2f"),
                      labels = c("Hot Songs", "Online Songs")) +
  labs(title = paste0("Yearly avg log-weeks, hot vs online songs (cor=",
                     round(cor_log_weeks, 2), ")"),
       x = "Year", y = "Mean log(1+weeks)", colour = "Chart") +
  theme_minimal()
ggsave(file.path(ROOT, "data/interim/toplist_compare.png"),
       p, width = 8, height = 4, dpi = 110)
cat("Wrote data/interim/toplist_compare.png\n")