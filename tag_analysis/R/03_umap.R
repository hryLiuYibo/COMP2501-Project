# 03_umap.R
# Map of songs on a 2-D layout, coloured by year. Right now we only
# have *chart metadata* features (peak rank, weeks, top_ids), so the
# map only reflects "when/how hot" the song was. Once audio
# embeddings arrive, the same scaffolding loads them instead.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2); library(Rtsne)
})

ROOT <- normalizePath(".")
mat <- read_csv(file.path(ROOT, "data", "interim/song_year_all.csv"),
                 show_col_types = FALSE) %>%
  filter(!is.na(year)) %>%
  mutate(
    log_weeks = log1p(weeks_total),
    inv_peak = 1 / log1p(peak_rank_min)
  )

X <- as.matrix(mat[, c("log_weeks", "inv_peak", "top_ids_present")])
X <- scale(X)

set.seed(20251002)
tsne <- Rtsne(X, dims = 2, perplexity = 30, verbose = FALSE,
              check_duplicates = FALSE)
mat$tsne1 <- tsne$Y[, 1]
mat$tsne2 <- tsne$Y[, 2]

p <- ggplot(mat, aes(tsne1, tsne2, label = song_title)) +
  geom_point(aes(colour = factor(year)), alpha = 0.55, size = 1.2) +
  labs(title = "t-SNE on chart-history features (QQ Hot Songs + Online Songs)",
       x = "t-SNE 1", y = "t-SNE 2", colour = "Year") +
  theme_minimal() +
  theme(legend.position = "right")
ggsave(file.path(ROOT, "data/interim/tsne_chart_meta.png"),
       p, width = 8, height = 5, dpi = 110)
cat("Wrote data/interim/tsne_chart_meta.png (",
    nrow(mat), " song-year rows)\n", sep = "")