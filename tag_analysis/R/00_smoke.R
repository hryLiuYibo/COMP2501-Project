# 00_smoke.R — first sanity test: load the CSV we just collected and
# confirm we can drive a one-shot plot.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
})
df <- read_csv("data/raw/netease/netease_playlist_6725984667.csv",
               show_col_types = FALSE)
cat("rows:", nrow(df), " cols:", ncol(df), "\n")
cat("first 3 rows:\n")
print(head(df[, c("track_id","title","artist","album","year")], 3))

# distribution of publish years (proxy for year_hint)
print(table(df$year, useNA = "ifany"))
print(table(df$duration_ms / 1000 > 360)) # >6min, mix or live?

# quick histogram
ggplot(df, aes(x = duration_ms / 1000)) +
  geom_histogram(bins = 40, fill = "#3964fe") +
  labs(title = "Duration distribution — first playlist",
       x = "Duration (s)", y = "Songs") +
  theme_minimal()
ggsave("data/interim/smoke_duration.png", width = 6, height = 4)
cat("plot saved to data/interim/smoke_duration.png\n")