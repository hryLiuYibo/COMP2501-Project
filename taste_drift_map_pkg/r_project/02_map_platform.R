# =============================================================================
# 02_map_platform.R — 结论 1：两个平台的品味差异
# -----------------------------------------------------------------------------
# 左：同年度两平台质心夹角（控制年份后反而更大）
# 右：单曲可分性 AUC + bootstrap 置信区间（R 端自己做 bootstrap）
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

q1     <- read_data("metrics_q1.csv")
margins <- read_data("margins.csv") |> mutate(platform = as_platform(platform))
V      <- read_data("vectors.csv")
V512   <- read_data("song_vectors_512.csv")

# ------------------------------------------------- R 端算同年度质心夹角
dims <- grep("^dim_", names(V512), value = TRUE)
M    <- as.matrix(V512[, dims])
sid  <- V512$song_id

angle_deg <- function(a, b) {
  acos(pmax(-1, pmin(1, sum(a * b) / (sqrt(sum(a * a)) * sqrt(sum(b * b)))))) * 180 / pi
}
cent_of_ids <- function(ids) {
  v <- colMeans(M[sid %in% ids, , drop = FALSE])
  v / sqrt(sum(v * v))
}
songs_in <- function(pf, y) unique(V$song_id[V$platform == pf & V$year == y])

years_both <- sort(intersect(unique(V$year[V$platform == "QQ Music"]),
                             unique(V$year[V$platform == "NetEase Cloud Music"])))
same_year <- do.call(rbind, lapply(years_both, function(y) {
  iq <- songs_in("QQ Music", y); inx <- songs_in("NetEase Cloud Music", y)
  data.frame(year = y, n_qq = length(iq), n_ne = length(inx),
             angle = angle_deg(cent_of_ids(iq), cent_of_ids(inx)))
})) |>
  filter(n_qq >= 4 & n_ne >= 4)   # 样本太少（如 2024）不给画

full_angle <- q1$value[q1$metric == "centroid_angle_deg"]

p_left <- ggplot(same_year, aes(factor(year), angle)) +
  geom_hline(yintercept = full_angle, linetype = "dashed", linewidth = 0.6,
             colour = COL_DARK) +
  geom_col(fill = COL_ACC, alpha = 0.88, width = 0.55) +
  geom_text(aes(label = sprintf("%.1f\u00b0", angle)), vjust = -0.5,
            size = 3.8, fontface = "bold", colour = COL_DARK) +
  labs(
    title = "Same-year centroid angles are LARGER (7-9\u00b0)",
    subtitle = sprintf("Dashed line = full-period %.2f\u00b0 (year mix, not platform style)", full_angle),
    x = NULL, y = "Centroid angle (degrees)"
  ) +
  theme_taste() +
  theme(panel.grid.major.x = element_blank())

# ---------------------------------------------------------------- 右图：AUC bootstrap
# AUC = P(随机 QQ 歌的 margin > 随机网易云歌的 margin)；0.5 = 完全分不开
qq_m <- margins$margin[margins$platform == "QQ Music"]
ne_m <- margins$margin[margins$platform == "NetEase Cloud Music"]

auc_stat <- function(qq, ne) mean(outer(qq, ne, ">")) + 0.5 * mean(outer(qq, ne, "=="))
auc_point <- auc_stat(qq_m, ne_m)

B <- 2000
auc_boot <- replicate(B, auc_stat(sample(qq_m, length(qq_m), replace = TRUE),
                                  sample(ne_m, length(ne_m), replace = TRUE)))
ci <- quantile(auc_boot, c(0.025, 0.975))

p_right <- ggplot(data.frame(auc = auc_boot), aes(auc)) +
  geom_histogram(bins = 34, fill = COL_ACC, alpha = 0.85,
                 colour = "white", linewidth = 0.15) +
  geom_vline(xintercept = auc_point, colour = COL_DARK, linewidth = 0.8) +
  geom_vline(xintercept = ci, colour = COL_GREY, linetype = "dashed", linewidth = 0.55) +
  geom_vline(xintercept = 0.5, colour = COL_QQ, linetype = "dotted", linewidth = 0.7) +
  annotate("text", x = 0.5, y = Inf, hjust = -0.05, vjust = 1.4, size = 2.9,
           colour = COL_QQ, label = "0.5 = cannot tell apart") +
  annotate("text", x = auc_point, y = Inf, hjust = -0.08, vjust = 2.2, size = 3.4,
           fontface = "bold", colour = COL_DARK,
           label = sprintf("AUC = %.3f\n95%% CI [%.3f, %.3f]", auc_point, ci[1], ci[2])) +
  labs(
    title = "Single songs CAN be told apart, but far from perfectly",
    subtitle = sprintf("Bootstrap over %d resamples: difference lives in song selection", B),
    x = "Per-song separability AUC", y = "Bootstrap resamples"
  ) +
  theme_taste() +
  theme(panel.grid.major.x = element_blank())

# ---------------------------------------------------------------- 拼图
library(patchwork)
p <- p_left + p_right +
  plot_layout(widths = c(1, 1.25)) +
  plot_annotation(
    title = "Platform difference: average taste nearly identical, song mix different",
    theme = theme(
      plot.title = element_text(colour = COL_DARK, face = "bold",
                                size = 15, hjust = 0.5),
      plot.background = element_rect(fill = "white", colour = NA)
    )
  )
save_fig(p, "map_platform.png", width = 13.0, height = 4.7)

# 把 bootstrap 结果也落盘，deck 文字引用
write_lines(
  sprintf("auc_point,%.4f\nci_lo,%.4f\nci_hi,%.4f\nB,%d", auc_point, ci[1], ci[2], B),
  file.path(RP_DIR, "auc_bootstrap.txt"))
