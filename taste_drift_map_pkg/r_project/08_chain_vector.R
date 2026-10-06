# =============================================================================
# 08_chain_vector.R — 原理链 ③：编码与聚合
# -----------------------------------------------------------------------------
# 左大图：17 个窗口 × 512 维向量热图（红正蓝负）
# 右上：歌曲向量里绝对值最大的 28 维
# 右下：窗口两两余弦（平均 0.887 —— 同一段落的歌取平均是安全的）
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

library(patchwork)

wv  <- read_data("probe_windows.csv")
pcos <- read_data("probe_chain.csv")

# ---- 左：窗口×维度热图
mat <- wv |>
  pivot_longer(starts_with("dim_"), names_to = "dim", values_to = "v") |>
  mutate(dim = as.integer(sub("dim_", "", dim)),
         window = factor(sprintf("w%d", window), levels = sprintf("w%d", 17:1)))
vmax <- max(abs(mat$v))

p_mat <- ggplot(mat, aes(dim, window, fill = v)) +
  geom_raster() +
  scale_fill_gradient2(low = COL_NE, mid = "white", high = COL_QQ,
                       midpoint = 0, limits = c(-vmax, vmax), name = NULL) +
  scale_x_continuous(breaks = c(1, 100, 200, 300, 400, 500), expand = c(0, 0)) +
  labs(title = "Each 10 s window \u2192 a 512-dim vector",
       x = "Dimension", y = "Window") +
  theme_taste() +
  theme(panel.grid = element_blank(),
        axis.text = element_text(colour = COL_GREY, size = rel(0.75)),
        legend.position = "right",
        legend.key.width = unit(0.28, "cm"),
        plot.title = element_text(size = rel(0.95)))

# ---- 右上：歌曲向量（窗口平均）绝对值最大的 28 维
song_vec <- colMeans(as.matrix(wv[, grep("^dim_", names(wv), value = TRUE)]))
top28 <- order(abs(song_vec), decreasing = TRUE)[1:28] |> sort()
df_top <- data.frame(dim = factor(top28, levels = top28), v = song_vec[top28])

p_top <- ggplot(df_top, aes(dim, v)) +
  geom_col(fill = COL_ACC, width = 0.72) +
  labs(title = "The final song vector: top 28 dims by |value|",
       x = "Dimension (sorted by index)", y = "Value") +
  theme_taste() +
  theme(panel.grid.major.x = element_blank(),
        axis.text.x = element_text(size = rel(0.6), angle = 90),
        plot.title = element_text(size = rel(0.82)))

# ---- 右下：窗口两两余弦
wmax <- 17
pcos_f <- pcos |>
  mutate(i = factor(window_i, levels = wmax:1),
         j = factor(window_j, levels = 1:wmax))
mcos <- mean(pcos$cosine[pcos$window_i != pcos$window_j])

p_cos <- ggplot(pcos_f, aes(j, i, fill = cosine)) +
  geom_tile() +
  scale_fill_gradient(low = "#FDFDF6", high = "#0E5C2F", name = NULL,
                      breaks = c(0.4, 0.6, 0.8, 1.0)) +
  scale_x_discrete(breaks = c(1, 5, 9, 13, 17)) +
  scale_y_discrete(breaks = c(1, 5, 9, 13, 17)) +
  labs(title = sprintf("Window-to-window cosine (avg %.3f)", mcos),
       x = "Window", y = "Window") +
  theme_taste() +
  theme(panel.grid = element_blank(),
        axis.text = element_text(colour = COL_GREY, size = rel(0.75)),
        legend.position = "right",
        legend.key.width = unit(0.28, "cm"),
        plot.title = element_text(size = rel(0.82)))

p_right <- p_top / p_cos + plot_layout(heights = c(1, 1.18))

p <- p_mat + p_right +
  plot_layout(widths = c(1.42, 1)) +
  plot_annotation(
    title = "Step 3 - encode & pool: 17 window vectors \u2192 average \u2192 L2 \u2192 one point on the unit sphere",
    theme = theme(
      plot.title = element_text(colour = COL_DARK, face = "bold",
                                size = 14, hjust = 0.5),
      plot.background = element_rect(fill = "white", colour = NA)
    )
  )
save_fig(p, "chain_3_vector.png", width = 13.0, height = 4.85)
