# =============================================================================
# 09_chain_similarity.R — 原理链 ④：相似度 = 夹角
# -----------------------------------------------------------------------------
# 《雪 Distance》与库内 386 首的余弦相似度直方图
# 关键教学点：窄锥效应 —— 所有余弦挤在 0.7~0.9，没有分散在 0 附近
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

sim <- read_data("probe_similarity.csv")
m   <- read_data("probe_meta.csv")

self_cos  <- 1.0
lib_mean  <- m$mean_cos_in_lib[1]
song_lab  <- sprintf("%s - %s", m$title[1], m$artist[1])

p <- ggplot(sim, aes(cosine_to_probe)) +
  geom_vline(xintercept = self_cos, colour = COL_QQ, linewidth = 0.9) +
  geom_vline(xintercept = lib_mean, colour = COL_NE, linetype = "dashed",
             linewidth = 0.65) +
  geom_histogram(bins = 46, fill = COL_ACC, alpha = 0.85,
                 colour = "white", linewidth = 0.15) +
  annotate("text", x = self_cos, y = Inf, hjust = -0.06, vjust = 1.6,
           size = 3.0, fontface = "bold", colour = COL_QQ,
           label = "itself = 1.000") +
  annotate("text", x = lib_mean, y = Inf, hjust = 1.06, vjust = 1.6,
           size = 3.0, colour = COL_NE,
           label = sprintf("library mean = %.3f", lib_mean)) +
  annotate("text", x = 0.315, y = 52, size = 3.0, colour = COL_GREY, hjust = 0,
           label = "everything crowds into 0.7-0.9:\nthe \"narrow cone\" of contrastive audio models") +
  scale_x_continuous(breaks = seq(0.2, 1.0, 0.1)) +
  scale_y_continuous(limits = c(0, 108), expand = expansion(mult = c(0, 0))) +
  labs(
    title = sprintf("Step 4 - similarity is just the angle: cosine of \"%s\" to all 386 library songs", song_lab),
    x = "Cosine similarity", y = "Number of songs"
  ) +
  theme_taste() +
  theme(panel.grid.major.x = element_blank())

save_fig(p, "chain_4_similarity.png", width = 13.0, height = 4.35)
