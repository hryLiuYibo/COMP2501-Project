# =============================================================================
# 01_map_overview.R — 品味地图总览
# -----------------------------------------------------------------------------
# 画两件事：
#   (a) 386 首上榜歌曲在 PCA 前两主成分上的散点，按平台着色
#   (b) 同一首歌在两个平台的上榜重合情况（条形）
# 结论：两平台共享同一片区域，没有分成两团。
# =============================================================================

# --- 自定位：无论从哪个目录运行，都能找到 _common.R -------------------------
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

vec  <- read_data("vectors.csv") |> mutate(platform = as_platform(platform))
sg   <- read_data("songs.csv")
var  <- read_data("pca_var.csv")

pc1_lab <- sprintf("PC1 (%.1f%% var)", 100 * var$explained_var[1])
pc2_lab <- sprintf("PC2 (%.1f%% var)", 100 * var$explained_var[2])

# 散点：同一首歌上榜多次只画一个点（按 song_id 去重）
pts <- vec |> distinct(song_id, .keep_all = TRUE)
n_qq <- sum(pts$platform == "QQ Music")
n_ne <- sum(pts$platform == "NetEase Cloud Music")

# --- 重合分类：deck 口径 = 唯一歌名（title_norm），同一首歌两个音频文件只算一次
cls <- sg |>
  mutate(overlap = factor(overlap_class,
                          levels = c("Both platforms", "QQ Music only", "NetEase only"))) |>
  distinct(title_norm, overlap) |>
  count(overlap)
n_both <- cls$n[cls$overlap == "Both platforms"]
pct    <- 100 * n_both / sum(cls$n)

# --- 库质心（全部歌曲的单位向量平均再归一化，但这里直接用 PC 坐标均值也可近似；
#     真正质心由 Python 端算好，这里画「几何中心」只作视觉参考）
ctr <- vec |> summarise(PC1 = mean(PC1), PC2 = mean(PC2))

# ---------------------------------------------------------------- 左图：散点
p_scatter <- ggplot(pts, aes(PC1, PC2, colour = platform)) +
  geom_point(alpha = 0.62, size = 1.7) +
  stat_ellipse(level = 0.68, linewidth = 0.7, linetype = "22", alpha = 0.85) +
  geom_point(data = ctr, aes(PC1, PC2), inherit.aes = FALSE,
             shape = 8, size = 3.4, colour = COL_DARK, stroke = 1.1) +
  annotate("text", x = ctr$PC1, y = ctr$PC2, label = "library centroid",
           vjust = -1.1, hjust = -0.06, size = 3.1, colour = COL_DARK) +
  scale_colour_manual(values = PLAT_COLORS,
                      labels = c(sprintf("QQ Music (%d)", n_qq),
                                 sprintf("NetEase (%d)", n_ne))) +
  labs(
    title = "All charting songs, projected on the first two principal components",
    x = pc1_lab, y = pc2_lab
  ) +
  theme_taste() +
  theme(legend.position = c(0.02, 0.98), legend.justification = c(0, 1),
        legend.background = element_rect(fill = alpha("white", 0.75), colour = NA))

# ---------------------------------------------------------------- 右图：重合
p_bar <- ggplot(cls, aes(n, overlap, fill = overlap)) +
  geom_col(width = 0.62) +
  geom_text(aes(label = n), hjust = -0.28, size = 4.0,
            colour = COL_DARK, fontface = "bold") +
  scale_fill_manual(values = c("Both platforms"     = COL_ACC,
                               "QQ Music only"      = COL_QQ,
                               "NetEase only"       = COL_NE)) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.18))) +
  labs(
    title = "Same song appearing on both platforms",
    subtitle = sprintf("Only %.0f%% overlap (%d of %d unique song titles)",
                       pct, n_both, sum(cls$n)),
    x = "Number of unique songs", y = NULL
  ) +
  theme_taste() +
  theme(legend.position = "none",
        panel.grid.major.y = element_blank(),
        axis.text.y = element_text(colour = COL_DARK, size = rel(0.95)))

# ---------------------------------------------------------------- 拼图
if (requireNamespace("patchwork", quietly = TRUE)) {
  library(patchwork)
  p <- p_scatter + p_bar +
    plot_layout(widths = c(2.15, 1)) +
    plot_annotation(
      title = "Taste Drift Map - the two platforms share one region of taste space",
      theme = theme(
        plot.title = element_text(colour = COL_DARK, face = "bold",
                                  size = 15, hjust = 0.5),
        plot.background = element_rect(fill = "white", colour = NA)
      )
    )
  save_fig(p, "map_overview.png", width = 13.0, height = 5.15)
} else {
  save_fig(p_scatter, "map_overview.png", width = 13.0, height = 4.6)
}
