# 01_clean.R
# Read QQ toplist long CSV -> one row per (year, song_id) with summary
# metrics (weeks_on_chart, peak_rank, year_avg_rank).
# Also merge in a `year` column derived from `period` (YYYY_WNN or
# YYYY-MM-DD).
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(stringr); library(rlang)
})

ROOT <- normalizePath(".")
RAW_QQ <- file.path(ROOT, "data", "raw", "qq")
cat("ROOT:", ROOT, "\n")
cat("RAW_QQ:", RAW_QQ, "\n")

# list available topIds
fps <- list.files(RAW_QQ, pattern = "_long[.]csv$", full.names = TRUE)
cat("Found", length(fps), "raw files:\n  ",
    paste(basename(fps), collapse = "\n  "), "\n")

read_one <- function(fp) {
  d <- read_csv(fp, show_col_types = FALSE)
  d <- d %>%
    mutate(
      year = as.integer(str_extract(period, "^[0-9]{4}")),
      week = suppressWarnings(as.integer(str_extract(period, "(?<=_)[0-9]+"))),
      song_key = paste0(song_id)
    )
  # collapse aliased top_titles: 喜力电音榜/电音榜 -> 电音榜
  # 抖快榜/抖音排行榜/抖音热歌榜 -> 抖音热歌榜
  alias <- c(
    "喜力电音榜" = "电音榜",
    "电音榜"     = "电音榜",
    "抖快榜"     = "抖音热歌榜",
    "抖音排行榜" = "抖音热歌榜",
    "抖音热歌榜" = "抖音热歌榜"
  )
  d$top_title <- unname(ifelse(d$top_title %in% names(alias),
                              alias[d$top_title],
                              d$top_title))
  d
}

raw <- bind_rows(lapply(fps, read_one))
cat("raw rows:", nrow(raw), "\n")

# per-song-year summary
song_year <- raw %>%
  filter(!is.na(.data$year)) %>%
  group_by(.data$top_id, .data$top_title, .data$song_id,
           .data$song_title, .data$singer_name,
           .data$album_mid, .data$year) %>%
  summarise(
    weeks_on_chart = n_distinct(.data$period),
    peak_rank = min(.data$rank, na.rm = TRUE),
    mean_rank = mean(.data$rank, na.rm = TRUE),
    genres = paste(sort(unique(na.omit(.data$genre_inferred))),
                   collapse = ","),
    .groups = "drop"
  )

# aggregate across topIds for "national taste" snapshot
song_year_all <- song_year %>%
  group_by(.data$year, .data$song_id, .data$song_title,
           .data$singer_name, .data$album_mid) %>%
  summarise(
    top_ids_present = n_distinct(.data$top_id),
    weeks_total = sum(.data$weeks_on_chart),
    peak_rank_min = min(.data$peak_rank),
    mean_rank_avg = weighted.mean(.data$mean_rank, w = .data$weeks_on_chart),
    genres = paste(sort(unique(unlist(strsplit(paste(.data$genres, collapse=","), ",")))),
                   collapse=","),
    .groups = "drop"
  ) %>%
  mutate(genres = ifelse(.data$genres == "" | is.na(.data$genres),
                         "unknown", .data$genres))

out_dir <- file.path(ROOT, "data", "interim")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
write_csv(song_year,
          file.path(out_dir, "song_year_by_topid.csv"))
write_csv(song_year_all,
          file.path(out_dir, "song_year_all.csv"))
write_csv(raw, file.path(out_dir, "qq_raw_long.csv"))

cat("wrote:\n",
    "  data/interim/song_year_by_topid.csv  (", nrow(song_year), ")\n",
    "  data/interim/song_year_all.csv        (", nrow(song_year_all), ")\n",
    "  data/interim/qq_raw_long.csv          (", nrow(raw), ")\n", sep = "")

# quick pivot summary: top-5 song per year (by peak rank then weeks)
top_per_year <- song_year_all %>%
  arrange(.data$year, .data$peak_rank_min, desc(.data$weeks_total)) %>%
  group_by(.data$year) %>% slice_head(n = 5) %>% ungroup()
print(top_per_year, n = 100)