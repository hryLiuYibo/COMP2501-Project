# 09_genre_drift.R
# Year-over-year share of songs that appeared on genre-tagged charts:
# rap (topId=58), edm (topId=57), guofeng (topId=65). These are the
# only genre labels we can infer from the public QQ API.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(ggplot2)
})

ROOT <- normalizePath(".")
song_year_all <- read_csv(file.path(ROOT, "data/interim/song_year_all.csv"),
                          show_col_types = FALSE) %>%
  filter(!is.na(year), year >= 2018)

genre_year <- song_year_all %>%
  separate_rows(genres, sep = ",") %>%
  filter(genres != "unknown", genres != "") %>%
  group_by(year, genres) %>%
  summarise(
    n_songs = n_distinct(song_id),
    .groups = "drop"
  ) %>%
  group_by(year) %>%
  mutate(share = year / sum(year) * 0 + n_songs / sum(n_songs)) %>%
  ungroup()

cat("Genre-tagged songs by year:\n")
print(genre_year, max = 60)

p <- ggplot(genre_year,
            aes(year, share, colour = genres)) +
  geom_line(linewidth = 1) + geom_point(size = 2) +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1)) +
  labs(title = "Share of annual songs tagged with inferred genre (topId-derived)",
       x = "Year", y = "Share of songs (per year, on any chart)",
       colour = "Inferred genre") +
  theme_minimal()
ggsave(file.path(ROOT, "data/interim/genre_drift.png"),
       p, width = 8, height = 4.5, dpi = 110)
cat("Wrote data/interim/genre_drift.png\n")

# top-5 most-common songs by inferred genre
top_in_genre <- song_year_all %>%
  separate_rows(genres, sep = ",") %>%
  filter(genres != "unknown", genres != "") %>%
  group_by(genres, song_id, song_title, singer_name) %>%
  summarise(weeks_total = sum(weeks_total), .groups = "drop") %>%
  arrange(genres, desc(weeks_total)) %>%
  group_by(genres) %>% slice_head(n = 5) %>% ungroup()

cat("\nTop 5 songs per inferred genre:\n")
print(top_in_genre, max = 60)
write_csv(top_in_genre, file.path(ROOT, "data/interim/top_in_each_genre.csv"))