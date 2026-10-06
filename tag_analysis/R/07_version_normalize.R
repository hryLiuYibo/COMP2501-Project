# 07_version_normalize.R
# version / live / cover detection from song_title.
# QQ's public API does not expose a clean version flag; we approximate
# it with regex on the song_title column. Each (song_id) becomes a
# canonical_key by stripping cover markers, live/remix/draft suffixes.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(stringr)
})

ROOT <- normalizePath(".")
song_year_all <- read_csv(file.path(ROOT, "data/interim/song_year_all.csv"),
                          show_col_types = FALSE)

# rough version markers commonly used in Chinese music titles
LIVE_RE  <- "(?i)\\b(live|现场版?|现场|演唱会版|音乐会版|live版|纯享版)\\b"
COVER_RE <- "(?i)\\b(cover|翻唱|翻自|致敬版|致敬)\\b"
REMIX_RE <- "(?i)\\b(remix|混音|extended|dj版|dj remix|mashup|remaster(ed)?)\\b"
DRAFT_RE <- "(?i)\\b(demo|练习室|练习版|试唱|acoustic|unplugged|钢琴版|伴奏|纯音乐|纯人声)\\b"

song_year_all <- song_year_all %>%
  mutate(
    title_norm = str_trim(str_replace_all(.data$song_title, "\\s+", " ")),
    is_live  = str_detect(.data$title_norm, LIVE_RE),
    is_cover = str_detect(.data$title_norm, COVER_RE),
    is_remix = str_detect(.data$title_norm, REMIX_RE),
    is_draft = str_detect(.data$title_norm, DRAFT_RE)
  )

# canonical_key: strip parens and version markers, keep base name
canonical_strip <- function(t) {
  t <- str_replace_all(t, "\\([^()]*\\)", " ")  # remove (anything)
  t <- str_replace_all(t, "\\（[^（）]*\\）", " ")  # full-width
  t <- str_replace_all(t, "[（(](live|现场|remix|cover|翻唱|纯享|remastered|demo|acoustic|钢琴版|伴奏|纯人声|练习|练习室|演唱会|音乐会|extended|mashup|dj)[）)]", " ")
  t <- str_replace_all(t, "\\s+", " ")
  str_trim(t)
}
song_year_all$canonical_key <- canonical_strip(song_year_all$title_norm)

# for each (canonical_key, year, singer_name) keep only the
# "primary" version = the one with highest weeks_total
primary_per_year_key <- song_year_all %>%
  group_by(.data$canonical_key, .data$singer_name, .data$year) %>%
  slice_max(order_by = .data$weeks_total, n = 1, with_ties = FALSE) %>%
  ungroup() %>%
  select(.data$year, .data$canonical_key, .data$singer_name,
         .data$song_id, .data$song_title, .data$weeks_total,
         .data$peak_rank_min, .data$top_ids_present, .data$genres)

write_csv(primary_per_year_key,
          file.path(ROOT, "data/interim/song_year_canonical.csv"))
write_csv(song_year_all,
          file.path(ROOT, "data/interim/song_year_all_with_flags.csv"))

cat("Canonical unique (year, key, singer) rows:", nrow(primary_per_year_key), "\n")
cat("\nFlag totals (one song_id may be flagged many times):\n")
cat("  live :", sum(song_year_all$is_live), "\n")
cat("  cover:", sum(song_year_all$is_cover), "\n")
cat("  remix:", sum(song_year_all$is_remix), "\n")
cat("  draft:", sum(song_year_all$is_draft), "\n")
cat("\nExamples of titles flagged as live:\n")
print(song_year_all %>% filter(.data$is_live) %>%
        select(.data$year, .data$song_title, .data$singer_name,
               .data$weeks_total) %>% head(10),
      max = 30)
cat("\nExamples of titles flagged as cover:\n")
print(song_year_all %>% filter(.data$is_cover) %>%
        select(.data$year, .data$song_title, .data$singer_name,
               .data$weeks_total) %>% head(10),
      max = 30)