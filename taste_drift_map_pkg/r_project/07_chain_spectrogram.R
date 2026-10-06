# =============================================================================
# 07_chain_spectrogram.R — 原理链 ②：从波形到频谱
# -----------------------------------------------------------------------------
# 左：线性 STFT（第 3 窗，10 秒）——人声乐器混在一起
# 右：对数梅尔频谱 —— CLAP 真正"看到"的输入
# 数据均由 Python 端按 deck 同参数导出（nperseg=2048, noverlap=1536, hann）
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

stft <- read_data("probe_stft.csv") |> mutate(bin = freq_khz)
mel  <- read_data("probe_mel.csv")

p1 <- ggplot(stft, aes(t_sec, freq_khz, fill = db)) +
  geom_raster(interpolate = TRUE) +
  scale_y_continuous(limits = c(0, 16), expand = c(0, 0)) +
  scale_fill_viridis_c(option = "magma", name = "dB") +
  labs(title = "Linear spectrogram (STFT)",
       x = "Time in window (s)", y = "Frequency (kHz)") +
  theme_taste() +
  theme(panel.grid = element_blank(),
        legend.title = element_text(size = 8, colour = COL_GREY),
        legend.key.height = unit(0.55, "cm"),
        axis.text.y = element_text(colour = COL_GREY, size = rel(0.82)))

p2 <- ggplot(mel, aes(t_sec, mel_bin, fill = db)) +
  geom_raster(interpolate = TRUE) +
  scale_y_continuous(breaks = c(1, 16, 32, 48, 64), expand = c(0, 0)) +
  scale_fill_viridis_c(option = "magma", name = "dB") +
  labs(title = "Log-Mel spectrogram  \u2190 what the model actually sees",
       x = "Time in window (s)", y = "Mel band (low freq at bottom)") +
  theme_taste() +
  theme(panel.grid = element_blank(),
        legend.title = element_text(size = 8, colour = COL_GREY),
        legend.key.height = unit(0.55, "cm"))

library(patchwork)
p <- (p1 + p2) +
  plot_annotation(
    title = "Step 2 - waveform to spectrogram: audio becomes a 2-D image (time axis info deliberately compressed)",
    theme = theme(
      plot.title = element_text(colour = COL_DARK, face = "bold",
                                size = 14.5, hjust = 0.5),
      plot.background = element_rect(fill = "white", colour = NA)
    )
  ) &
  theme(plot.margin = margin(10, 14, 8, 10))

save_fig(p, "chain_2_spectrogram.png", width = 13.0, height = 4.5)
