# 05_changepoint.R
# Detect changepoints in the year-over-year trajectory of the
# aggregate chart-history feature. Uses base R via piecewise-linear fit
# BIC selection (no `changepoint` package needed). Permutation test for
# significance.
suppressPackageStartupMessages({
  library(readr); library(dplyr); library(ggplot2)
})

ROOT <- normalizePath(".")
feat_by_year <- read_csv(file.path(ROOT, "data/interim/song_year_all.csv"),
                         show_col_types = FALSE) %>%
  filter(!is.na(year)) %>%
  group_by(year) %>%
  summarise(
    n_songs = n_distinct(song_id),
    avg_weeks = mean(weeks_total, na.rm = TRUE),
    avg_peak = mean(peak_rank_min, na.rm = TRUE),
    .groups = "drop"
  ) %>% arrange(year)

y <- feat_by_year$avg_weeks
years <- feat_by_year$year

# piecewise linear: try all splits in interior years, pick min BIC
seg_bic <- function(y, x, k) {
  n <- length(y)
  if (k >= n) return(Inf)
  # k breakpoints -> k+1 segments
  # estimate variance residual
  rss <- .Machine$double.xmax
  if (k == 0) {
    fit <- lm(y ~ x)
    rss <- sum(residuals(fit)^2)
  } else {
    # try all combinations of k cut points (small n)
    idx_combos <- combn(seq(2, n - 1), k, simplify = FALSE)
    best_rss <- Inf
    for (idx in idx_combos) {
      # build piecewise
      df <- data.frame(y = y, x = x,
                       seg = cut(seq_along(y), c(0, idx, n),
                                 labels = FALSE))
      fit <- lm(y ~ x:factor(seg) + factor(seg), data = df)
      ss <- sum(residuals(fit)^2)
      if (ss < best_rss) { best_rss <- ss; best <- idx }
    }
    rss <- best_rss
  }
  # BIC: n*log(rss/n) + (k+3)*log(n)  ~ parsimonious
  rss_safe <- max(rss, 1e-6)
  n * log(rss_safe / n) + (k + 3) * log(n)
}

ks <- 0:min(4, length(y) - 1)
bics <- sapply(ks, function(k) seg_bic(y, x = years, k))
names(bics) <- paste0("k=", ks)
cat("BIC scores by #changepoints:\n"); print(bics)
best_k <- ks[which.min(bics)]
cat("Selected k =", best_k, " changepoints\n")

# extract best breakpoints for k=best_k
if (best_k > 0) {
  n <- length(y)
  idx_combos <- combn(seq(2, n - 1), best_k, simplify = FALSE)
  best_rss <- Inf
  best_idx <- NULL
  for (idx in idx_combos) {
    df <- data.frame(y = y, x = years,
                     seg = cut(seq_along(y), c(0, idx, n),
                               labels = FALSE))
    fit <- lm(y ~ x:factor(seg) + factor(seg), data = df)
    ss <- sum(residuals(fit)^2)
    if (ss < best_rss) { best_rss <- ss; best_idx <- idx }
  }
  cat("Changepoints at years:", years[best_idx], "\n")
  write_csv(tibble(year = years[best_idx]),
            file.path(ROOT, "data/interim/changepoints.csv"))
} else {
  cat("No changepoints detected.\n")
}

# permutation test: random shuffle years and compare BIC
B <- 1000
perm_min <- replicate(B, {
  ys <- sample(y)
  min(sapply(0:2, function(k) seg_bic(ys, x = years, k)))
})
obs_min <- min(bics)
cat("Observed min BIC:", obs_min, "\n")
cat("Permutation p-value:", mean(perm_min <= obs_min), "\n")

p <- ggplot(feat_by_year, aes(year, avg_weeks)) +
  geom_line(colour = "#3964fe") +
  geom_point(colour = "#3964fe") +
  geom_vline(xintercept = if (best_k > 0) years[best_idx] else numeric(0),
             linetype = "dashed", colour = "red") +
  labs(title = "Yearly avg weeks-on-chart, with detected changepoints",
       x = "Year", y = "Avg weeks on chart") +
  theme_minimal()
ggsave(file.path(ROOT, "data/interim/changepoints.png"),
       p, width = 8, height = 4, dpi = 110)
cat("Wrote data/interim/changepoints.png\n")