# =============================================================================
# 05_map_coverage.R — 数据边界：这份分析能回答什么、不能回答什么
# =============================================================================

{
  .find_common <- function() {
    cands <- character(0)
    for (i in rev(seq_len(sys.nframe()))) {
      of <- tryCatch(sys.frame(i)$ofile, error = function(e) NULL)
      if (is.character(of) && length(of) == 1 && nzchar(of)) {
        cands <- c(cands, dirname(normalizePath(of, mustWork = FALSE)))
      }
    }
    a <- commandArgs(trailingOnly = FALSE)
    f <- sub("^--file=", "", a[grep("^--file=", a)])
    if (length(f)) cands <- c(cands, dirname(normalizePath(f[1], mustWork = FALSE)))
    cands <- c(cands, getwd())
    for (d in unique(cands)) {
      if (file.exists(file.path(d, "_common.R"))) return(file.path(d, "_common.R"))
      up <- normalizePath(file.path(d, ".."), mustWork = FALSE)
      if (file.exists(file.path(up, "_common.R"))) return(file.path(up, "_common.R"))
    }
    stop("cannot locate _common.R from: ", paste(unique(cands), collapse = " | "))
  }
  source(.find_common())
}

cov <- read_data("coverage.csv") |>
  mutate(platform = as_platform(platform),
         year = factor(year),
         lab = sprintf("%d/%d", hits, in_chart))

p <- ggplot(cov, aes(year, hits, fill = platform)) +
  geom_col(position = position_dodge2(width = 0.9, preserve = "single"),
           alpha = 0.9, width = 0.86) +
  geom_text(aes(label = lab),
            position = position_dodge2(width = 0.9, preserve = "single"),
            vjust = -0.45, size = 2.75, colour = COL_DARK, fontface = "bold") +
  annotate("text", x = 7.15, y = 23, size = 3.0, colour = COL_QQ, hjust = 1,
           label = "QQ 2024 H2: audio missing (5/100)") +
  scale_fill_manual(values = PLAT_COLORS) +
  scale_y_continuous(limits = c(0, 96), expand = expansion(mult = c(0, 0))) +
  labs(
    title = "Local audio coverage: what this analysis can and cannot answer",
    subtitle = "Chart entries matched to a local audio file, per year",
    x = NULL, y = "Matched chart entries"
  ) +
  theme_taste() +
  theme(panel.grid.major.x = element_blank(),
        legend.position = "top", legend.justification = "right")

save_fig(p, "map_coverage.png", width = 13.0, height = 4.55)
