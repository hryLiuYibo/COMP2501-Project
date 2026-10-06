# =============================================================================
# 03_map_trajectory.R — 结论 2：品味如何变化
# -----------------------------------------------------------------------------
# 左：年度质心在 PCA 空间的轨迹（点大小 ∝ 该年歌曲数）
# 右：相邻年度漂移角 vs bootstrap 噪声带（R 端对 512 维向量自助重采样）
#
# 口径说明（与 Python 端 deck 一致）：一首歌若在多个年份上榜，则计入每个年份。
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

set.seed(2026)

var <- read_data("pca_var.csv")
cen <- read_data("centroid_pc.csv") |> mutate(platform = as_platform(platform))
V   <- read_data("vectors.csv")                      # 榜单记录级（含重复上榜）

pc1_lab <- sprintf("PC1 (%.1f%% var)", 100 * var$explained_var[1])
pc2_lab <- sprintf("PC2 (%.1f%% var)", 100 * var$explained_var[2])

# ---------------------------------------------------------------- 左图：年度轨迹
library(ggrepel)
cen_lab <- cen |> mutate(lab = sprintf("%d", year))
p_left <- ggplot(cen, aes(PC1, PC2, colour = platform, group = platform)) +
  geom_path(arrow = arrow(length = unit(7, "pt"), type = "closed"),
            linewidth = 0.5, alpha = 0.5, linetype = "11") +
  geom_point(aes(size = n_songs, alpha = n_songs >= 8), shape = 16) +
  geom_text_repel(data = cen_lab, aes(label = lab, size = n_songs),
                  show.legend = FALSE, fontface = "bold",
                  segment.colour = NA, min.segment.length = 0,
                  max.overlaps = 20, seed = 7,
                  size = 2.6) +
  scale_colour_manual(values = PLAT_COLORS) +
  scale_size_continuous(range = c(2.2, 5.4), guide = "none") +
  scale_alpha_manual(values = c(`TRUE` = 0.9, `FALSE` = 0.35), guide = "none") +
  labs(
    title = "Yearly centroids wander in place (point size = songs that year)",
    subtitle = "Faded points = too few songs that year to trust",
    x = pc1_lab, y = pc2_lab
  ) +
  theme_taste() +
  theme(legend.position = c(0.02, 0.98), legend.justification = c(0, 1),
        legend.background = element_rect(fill = alpha("white", 0.75), colour = NA))

# ---------------------------------------------------------------- 右图：漂移 vs 噪声
V512 <- read_data("song_vectors_512.csv")
dims <- grep("^dim_", names(V512), value = TRUE)
M    <- as.matrix(V512[, dims])
sid  <- V512$song_id

# song_id -> 上榜年集合（一首歌可属多年）
song_years <- split(V$year, V$song_id)

angle_deg <- function(a, b) {
  acos(pmax(-1, pmin(1, sum(a * b) / (sqrt(sum(a * a)) * sqrt(sum(b * b)))))) * 180 / pi
}
# 位置索引（每首歌一行）；重采样必须带重复次数，否则 bootstrap 失效
row_of <- function(ids) match(ids, sid)
cent_of_rows <- function(rows) {
  v <- colMeans(M[rows, , drop = FALSE])
  v / sqrt(sum(v * v))
}

# 某平台某年的歌（按 song_id 去重）
songs_in <- function(pf, y) {
  unique(V$song_id[V$platform == pf & V$year == y])
}

# bootstrap：该年有放回抽歌（按行位置，保留重复）-> 质心 ->
# 与该年全量质心的夹角分布，取均值作为"质心自身的不确定度"
boot_shift <- function(idx, B = 300) {
  if (length(idx) < 4) return(NA_real_)
  rows <- row_of(idx)
  c0 <- cent_of_rows(rows)
  s <- numeric(B)
  for (b in seq_len(B)) {
    s[b] <- angle_deg(cent_of_rows(sample(rows, length(rows), replace = TRUE)), c0)
  }
  mean(s)
}

qq_years <- sort(unique(V$year[V$platform == "QQ Music"]))
qq_shift <- sapply(qq_years, function(y) boot_shift(songs_in("QQ Music", y)))
names(qq_shift) <- sprintf("%d-%d", qq_years, qq_years + 1)
noise_band <- range(qq_shift, na.rm = TRUE)

drift <- read_data("drift_annual.csv") |>
  mutate(lab = sprintf("%d-%d", year_from, year_to),
         collapsed = pmin(n_from, n_to) <= 4,
         platform = as_platform(platform)) |>
  filter(year_to <= 2024) |>
  left_join(
    tibble(lab = names(qq_shift), noise_sd = as.numeric(qq_shift)),
    by = "lab")

p_right <- ggplot(drift, aes(lab, drift_deg, fill = platform)) +
  geom_col(width = 0.72, alpha = 0.88,
           position = position_dodge2(width = 0.86, preserve = "single")) +
  geom_errorbar(
    data = filter(drift, platform == "QQ Music"),
    aes(ymin = drift_deg - noise_sd, ymax = drift_deg + noise_sd),
    width = 0.16, linewidth = 0.45, colour = COL_DARK, alpha = 0.7,
    position = position_dodge2(width = 0.86, preserve = "single")) +
  geom_text(aes(label = sprintf("%.1f\u00b0", drift_deg),
                group = platform,
                y = drift_deg + dplyr::coalesce(noise_sd, 0) + 0.55),
            position = position_dodge2(width = 0.86, preserve = "single"),
            vjust = 0, size = 2.6, fontface = "bold", colour = COL_DARK,
            show.legend = FALSE) +
  annotate("text", x = 4.05, y = 18.6, size = 2.75, colour = COL_QQ, hjust = 0.5,
           label = "2024: only 3 songs - sample collapse, not a trend") +
  geom_rect(xmin = 0.4, xmax = 6.6, ymin = noise_band[1], ymax = noise_band[2],
            fill = COL_GREY, alpha = 0.14, inherit.aes = FALSE) +
  scale_fill_manual(values = PLAT_COLORS) +
  scale_y_continuous(limits = c(0, 23), expand = expansion(mult = c(0, 0))) +
  labs(
    title = "Year-over-year drift mostly stays within the noise band",
    subtitle = sprintf("Grey band = QQ centroid shift under bootstrap (%.1f-%.1f\u00b0)",
                       noise_band[1], noise_band[2]),
    x = NULL, y = "Adjacent-year centroid drift (degrees)"
  ) +
  theme_taste() +
  theme(panel.grid.major.x = element_blank(),
        legend.position = "top", legend.justification = "right")

library(patchwork)
p <- p_left + p_right +
  plot_layout(widths = c(1.02, 1)) +
  plot_annotation(
    title = "Taste drift: vibration in place, no one-way migration",
    theme = theme(
      plot.title = element_text(colour = COL_DARK, face = "bold",
                                size = 15, hjust = 0.5),
      plot.background = element_rect(fill = "white", colour = NA)
    )
  )
save_fig(p, "map_trajectory.png", width = 13.0, height = 5.0)

write_lines(
  c(sprintf("%s_boot_shift,%.3f", names(qq_shift), qq_shift),
    sprintf("noise_band_lo,%.3f", noise_band[1]),
    sprintf("noise_band_hi,%.3f", noise_band[2])),
  file.path(RP_DIR, "bootstrap_noise.txt"))
