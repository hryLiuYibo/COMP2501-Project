# 15_covid_qq_features.R
# Extract QQ chart-history features that change during the
# COVID-Q1 2020 period (Wuhan lockdown 2020-01-23 through the end
# of nationwide stay-at-home in mid-April 2020).
#
# We compare:
#   pre-COVID baseline:  2018W30 .. 2019W52 (avg per week)
#   COVID-Q1 window  :  2020W04 .. 2020W17 (avg per week)
#   recovery window  :  2020W30 .. 2020W52 (avg per week)
#
# Features per week:
#   - unique songs entering chart
#   - songs that overlap with the previous week
#   - new-to-ever songs (i.e. first appearance in our window)
#   - mean weeks-on-chart for songs that fell off this week
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(ggplot2); library(stringr)
})

ROOT <- normalizePath(".")
raw <- read_csv(file.path(ROOT, "data/interim/qq_raw_long.csv"),
                show_col_types = FALSE) %>%
  filter(!is.na(year))

# Ensure period is parsed as year + week_number
raw <- raw %>%
  mutate(
    year_n = as.integer(str_extract(period, "^[0-9]{4}")),
    week_n = suppressWarnings(as.integer(str_extract(period, "(?<=_)[0-9]+"))),
    week_label = paste0(year_n, "_", sprintf("%02d", week_n))
  ) %>%
  filter(!is.na(week_n))

# Helper: assign period regime
classify_period <- function(yr, wk) {
  case_when(
    yr < 2020 ~ "pre_covid",
    yr == 2020 & wk <= 3  ~ "pre_covid_jan",
    yr == 2020 & wk >= 4 & wk <= 17 ~ "covid_q1",
    yr == 2020 & wk >= 18 & wk <= 26 ~ "covid_recovery",
    yr == 2020 & wk >= 27 ~ "post_covid",
    TRUE ~ "other"
  )
}
raw$regime <- classify_period(raw$year_n, raw$week_n)

# Per-week summary
weekly <- raw %>%
  group_by(week_label, regime, year_n, week_n) %>%
  summarise(
    n_rows = n(),
    n_unique_songs = n_distinct(song_id),
    .groups = "drop"
  ) %>%
  arrange(year_n, week_n)

# Per-week rolling new-song count vs prior week
weekly <- weekly %>%
  mutate(
    new_songs_this_week = NA_integer_,
  )
song_set <- list()
for (i in seq_len(nrow(weekly))) {
  yr <- weekly$year_n[i]; wk <- weekly$week_n[i]
  this_songs <- raw %>%
    filter(year_n == yr, week_n == wk) %>%
    distinct(song_id) %>% pull(song_id)
  if (i == 1) {
    weekly$new_songs_this_week[i] <- length(this_songs)
  } else {
    prev_year <- weekly$year_n[i - 1]; prev_week <- weekly$week_n[i - 1]
    prev_songs <- raw %>%
      filter(year_n == prev_year, week_n == prev_week) %>%
      distinct(song_id) %>% pull(song_id)
    weekly$new_songs_this_week[i] <- sum(!(this_songs %in% prev_songs))
  }
}

# Per-regime summary
regime_summary <- weekly %>%
  filter(regime %in% c("pre_covid", "covid_q1", "covid_recovery", "post_covid")) %>%
  group_by(regime) %>%
  summarise(
    n_weeks = n(),
    mean_unique_songs_per_week = mean(n_unique_songs),
    mean_new_songs_per_week   = mean(new_songs_this_week, na.rm = TRUE),
    .groups = "drop"
  )
cat("=== Per-regime QQ chart-history features ===\n")
print(regime_summary, n = Inf)

write_csv(regime_summary,
          file.path(ROOT, "data/interim/covid_period_features.csv"))

# Plot
p <- ggplot(weekly %>% filter(year_n >= 2019, year_n <= 2020),
            aes(week_n, n_unique_songs, colour = factor(year_n))) +
  geom_line(linewidth = 1) + geom_point(size = 2) +
  geom_vline(xintercept = 4, linetype = "dashed", colour = "red") +
  geom_vline(xintercept = 17, linetype = "dashed", colour = "orange") +
  annotate("text", x = 4, y = Inf, label = " Wuhan lockdown\n 2020-01-23",
           vjust = 1.5, hjust = -0.1, colour = "red") +
  annotate("text", x = 17, y = Inf, label = " stay-at-home\n ends",
           vjust = 1.5, hjust = -0.1, colour = "orange") +
  scale_colour_manual(values = c("2019" = "#3964fe", "2020" = "#fc7e2f")) +
  labs(title = "QQ unique chart songs per week, 2019 vs 2020",
       x = "Week number", y = "Unique songs this week",
       colour = "Year") +
  theme_minimal()
ggsave(file.path(ROOT, "data/interim/covid_period_qq_features.png"),
       p, width = 10, height = 5, dpi = 110)
cat("\nWrote data/interim/covid_period_qq_features.png\n")