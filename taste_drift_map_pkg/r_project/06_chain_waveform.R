# =============================================================================
# 06_chain_waveform.R — 原理链 ①：波形与切窗
# -----------------------------------------------------------------------------
# 数据：probe_waveform.csv（Python 端导出的 min/max 包络，视觉等价于逐采样点）
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

meta <- read_data("probe_meta.csv")
wf   <- read_data("probe_waveform.csv")

dur    <- meta$duration_sec[1]
n_win  <- meta$n_windows[1]
win_s  <- dur / n_win            # 10 s 窗
k      <- 2                      # 高亮第 3 窗（跳过 intro），与 deck 一致

title <- sprintf("Snow Distance - Capper / Luo Yan (%.0f s \u2192 %d non-overlapping 10 s windows)",
                 dur, n_win)

p <- ggplot(wf, aes(t_sec, xmin = t_sec, xmax = dplyr::lead(t_sec, default = dur),
                    ymin = amp_min, ymax = amp_max)) +
  geom_rect(fill = COL_ACC, colour = NA) +
  # 高亮窗口
  annotate("rect", xmin = k * win_s, xmax = (k + 1) * win_s,
           ymin = -1.02, ymax = 1.02, fill = COL_ORANGE, alpha = 0.20) +
  annotate("segment", x = k * win_s, xend = k * win_s, y = -1.02, yend = 1.02,
           colour = COL_ORANGE, linewidth = 0.55) +
  annotate("segment", x = (k + 1) * win_s, xend = (k + 1) * win_s,
           y = -1.02, yend = 1.02, colour = COL_ORANGE, linewidth = 0.55) +
  annotate("text", x = (k + 0.5) * win_s, y = 1.12, size = 3.2, fontface = "bold",
           colour = COL_ORANGE, label = sprintf("window %d", k + 1)) +
  coord_cartesian(xlim = c(0, dur), ylim = c(-1.02, 1.02), expand = FALSE) +
  scale_x_continuous(breaks = seq(0, 160, 20)) +
  labs(
    title = "From a song to a vector, step 1 - waveform & windowing",
    subtitle = title,
    x = "Time (seconds)", y = "Amplitude"
  ) +
  theme_taste() +
  theme(panel.grid.minor.y = element_blank())

save_fig(p, "chain_1_waveform.png", width = 13.0, height = 3.35)
