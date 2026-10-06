# 17_cross_region_patterns.R
# Cross-region patterns beyond song-overlap. We compare three
# snapshots on three non-overlap metrics:
#   (a) share of "old" songs in the top-N (release_year <= 2018)
#   (b) artist concentration (Gini coefficient on artist ranks)
#   (c) share of songs by the top-3 artists in the top-N
#
# We use these to support two QQ-derived claims:
#   1. "old songs keep re-entering QQ chart" -> is this a Chinese
#      music-market pattern, or a QQ-platform artefact?
#   2. "2022 platform split into Douyin-driven and QQ-driven"
#      -> is "star concentration" a Chinese music-market
#      pattern, or a QQ-platform artefact?
#
# If the SAME patterns appear on Apple Music CN (China via Apple)
# and are ABSENT on Apple Music US / Spotify Global, we have
# cross-region validation of the QQ findings.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(stringr); library(tidyr); library(ggplot2); library(scales)
})

ROOT <- normalizePath(".")

# Cutoff: anything released 2018 or earlier is "old"
OLD_CUTOFF <- 2018

# Gini coefficient helper
gini <- function(x) {
  if (length(x) == 0) return(NA_real_)
  x <- x[!is.na(x)]
  if (length(x) == 0) return(NA_real_)
  x <- sort(x)
  n <- length(x)
  sum_x <- sum(x)
  if (sum_x == 0) return(0)
  2 * sum((1:n) * x) / (n * sum_x) - (n + 1) / n
}

# Read each snapshot
qq_raw <- read_csv(file.path(ROOT, "data/raw/qq/qq_topId26_current_snapshot.csv"),
                   show_col_types = FALSE)
# QQ has no release_date column, but we have publish-year from the
# weekly CSV; for the current snapshot we approximate via song_id
# lookup into the canonical song-year table.
qq_year_all <- read_csv(file.path(ROOT, "data/interim/song_year_all.csv"),
                        show_col_types = FALSE) %>%
  select(song_id, year) %>%
  group_by(song_id) %>% summarise(year = min(year, na.rm = TRUE), .groups = "drop")

qq <- qq_raw %>%
  left_join(qq_year_all, by = c("song_id" = "song_id")) %>%
  mutate(name = song_title, artist = singer_name) %>%
  select(name, artist, year, rank)

ne <- read_csv(file.path(ROOT, "data/raw/netease/netease_hot_songs_3778678.csv"),
               show_col_types = FALSE) %>%
  mutate(rank = row_number(), name = title, artist = artist,
         year = as.integer(year)) %>%
  select(name, artist, year, rank)

am_cn <- read_csv(file.path(ROOT, "data/raw/apple_music/apple_music_cn_top50_2026-10-02.csv"),
                 show_col_types = FALSE) %>%
  mutate(year = as.integer(substr(release_date, 1, 4))) %>%
  select(name, artist = artist_name, year, rank)

am_us <- read_csv(file.path(ROOT, "data/raw/apple_music/apple_music_us_top50_2026-10-02.csv"),
                 show_col_types = FALSE) %>%
  mutate(year = as.integer(substr(release_date, 1, 4))) %>%
  select(name, artist = artist_name, year, rank)

sp_global <- read_csv(file.path(ROOT,
  "data/raw/spotify/spotify_regional_global_weekly_2026-10-02.csv"),
  show_col_types = FALSE) %>%
  mutate(year = as.integer(substr(release_date, 1, 4))) %>%
  select(name, artist = artists, year, rank)

# Some platforms have NAs in year (Spotify Global has all-NA). Keep
# only rows with year available for the year-based stats.
platforms <- list(
  `QQ`               = qq,
  `NetEase`          = ne,
  `Apple Music CN`   = am_cn,
  `Apple Music US`   = am_us,
  `Spotify Global`   = sp_global
)

# Compute (a) share-old and (b) artist Gini + (c) top-3 share
metrics <- lapply(names(platforms), function(nm) {
  d <- platforms[[nm]]
  d_old <- d %>% filter(!is.na(year))
  total <- nrow(d_old)
  n_old <- sum(d_old$year <= OLD_CUTOFF)
  share_old <- if (total > 0) n_old / total else NA_real_
  g <- gini(d_old$rank)
  artist_rank <- d_old %>% count(artist, name = "n_songs") %>%
    arrange(desc(n_songs))
  top3_share <- if (nrow(artist_rank) >= 3)
    sum(artist_rank$n_songs[1:3]) / sum(artist_rank$n_songs)
  else if (nrow(artist_rank) > 0)
    sum(artist_rank$n_songs[1:nrow(artist_rank)]) / sum(artist_rank$n_songs)
  else NA_real_
  tibble(platform = nm,
         n_top = nrow(d),
         n_with_year = total,
         share_old_pre2018 = round(share_old * 100, 1),
         artist_gini = round(g, 3),
         top3_artist_share_pct = round(top3_share * 100, 1))
})
metrics_df <- bind_rows(metrics)
cat("=== Cross-region patterns (snapshot 2026-10-02) ===\n")
print(metrics_df, n = Inf)
write_csv(metrics_df,
          file.path(ROOT, "data/interim/cross_region_patterns.csv"))

# Bar plot: share-old
p1 <- ggplot(metrics_df,
             aes(reorder(platform, share_old_pre2018), share_old_pre2018,
                 fill = platform)) +
  geom_col() +
  geom_text(aes(label = paste0(share_old_pre2018, "%")), vjust = -0.5, size = 3.5) +
  labs(title = "Share of top-N songs released 2018 or earlier",
       subtitle = "Higher = older catalogue",
       x = NULL, y = "% of top-N released in 2018 or earlier") +
  scale_y_continuous(labels = function(x) paste0(x, "%")) +
  theme_minimal() +
  theme(legend.position = "none")
ggsave(file.path(ROOT, "data/interim/cross_region_share_old.png"),
       p1, width = 7, height = 4, dpi = 110)

# Bar plot: artist Gini
p2 <- ggplot(metrics_df,
             aes(reorder(platform, artist_gini), artist_gini,
                 fill = platform)) +
  geom_col() +
  geom_text(aes(label = artist_gini), vjust = -0.5, size = 3.5) +
  labs(title = "Artist rank concentration (Gini)",
       subtitle = "Higher = star-driven, lower = distributed",
       x = NULL, y = "Gini coefficient") +
  theme_minimal() +
  theme(legend.position = "none")
ggsave(file.path(ROOT, "data/interim/cross_region_artist_gini.png"),
       p2, width = 7, height = 4, dpi = 110)

# Bar plot: top-3 artist share
p3 <- ggplot(metrics_df,
             aes(reorder(platform, top3_artist_share_pct), top3_artist_share_pct,
                 fill = platform)) +
  geom_col() +
  geom_text(aes(label = paste0(top3_artist_share_pct, "%")), vjust = -0.5, size = 3.5) +
  labs(title = "Top-3 artists' share of top-N",
       subtitle = "Higher = same few artists dominate",
       x = NULL, y = "% of top-N from top-3 artists") +
  scale_y_continuous(labels = function(x) paste0(x, "%")) +
  theme_minimal() +
  theme(legend.position = "none")
ggsave(file.path(ROOT, "data/interim/cross_region_top3_share.png"),
       p3, width = 7, height = 4, dpi = 110)

cat("\nWrote data/interim/cross_region_{share_old,artist_gini,top3_share}.png\n")
cat("Wrote data/interim/cross_region_patterns.csv\n")