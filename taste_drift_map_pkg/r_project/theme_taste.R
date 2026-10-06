# =============================================================================
# theme_taste.R — 共享主题与配色
# -----------------------------------------------------------------------------
# 所有图表脚本都 source() 这个文件，保证视觉一致（也方便一次改全局）。
# 配色沿用原 deck 的设计语言：QQ = 红，网易云 = 蓝，强调色 = 绿。
#
# 路径解析：本文件被 source() 时会从调用栈里找到调用方脚本的路径，
# 从而把 ROOT 锚定到 r_project/ 的上一级（taste_map/），
# 这样无论从哪个目录运行结果都一致。
# =============================================================================

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(readr)
  library(tidyr)
  library(scales)
})

# ------------------------------------------------------------------ 路径解析
# 找出 r_project/ 目录本身（不是调用者所在目录）。
# 依次尝试：调用栈里的 ofile（source() 场景）→ --file=（Rscript 场景）→ getwd()，
# 取第一个真正含 theme_taste.R 的候选，避免"多套一层目录"。
.detect_dir <- function() {
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
    for (up in 0:2) {
      p <- if (up == 0) d else normalizePath(file.path(d, strrep("../", up)), mustWork = FALSE)
      if (file.exists(file.path(p, "theme_taste.R"))) return(p)
    }
  }
  getwd()
}

RP_DIR  <- .detect_dir()
DATA   <- file.path(RP_DIR, "data")
# 图统一输出到仓库根的 figures/ —— build_pptx_en.py 直接从那里取图，
# 与 Python 端（make_map_figs.py / make_chain_figs.py）的产物放在一起。
REPO   <- normalizePath(file.path(RP_DIR, ".."), mustWork = FALSE)
FIGDIR <- file.path(REPO, "figures")
dir.create(FIGDIR, showWarnings = FALSE)

# ------------------------------------------------------------------ 配色
COL_QQ   <- "#DC2626"   # QQ Music  — red
COL_NE   <- "#2563EB"   # NetEase   — blue
COL_ACC  <- "#1DB954"   # 强调 / 单一量 — green
COL_DARK <- "#10131A"
COL_GREY <- "#6B7280"
COL_ORANGE <- "#F59E0B"
COL_GRID <- "#E3E6EB"

PLAT_COLORS <- c("QQ Music" = COL_QQ, "NetEase Cloud Music" = COL_NE)

# 平台名的展示顺序（图例、分面都用它）
PLAT_LEVELS <- c("QQ Music", "NetEase Cloud Music")

# ------------------------------------------------------------------ 主题
# 白底、无边框、淡网格 —— 幻灯片投影友好（不靠灰底衬托）
theme_taste <- function(base_size = 12, base_family = "sans") {
  theme_minimal(base_size = base_size, base_family = base_family) +
    theme(
      plot.background   = element_rect(fill = "white", colour = NA),
      panel.background  = element_rect(fill = "white", colour = NA),
      panel.grid.major  = element_line(colour = COL_GRID, linewidth = 0.35),
      panel.grid.minor  = element_blank(),
      axis.line.x       = element_line(colour = "#D1D5DB", linewidth = 0.4),
      axis.ticks.x      = element_line(colour = "#D1D5DB", linewidth = 0.4),
      axis.ticks.y      = element_blank(),
      axis.text         = element_text(colour = COL_GREY, size = rel(0.82)),
      axis.title        = element_text(colour = COL_GREY, size = rel(0.92)),
      plot.title        = element_text(colour = COL_DARK, face = "bold",
                                       size = rel(1.18), hjust = 0.5,
                                       margin = margin(b = 6)),
      plot.subtitle     = element_text(colour = COL_GREY, size = rel(0.86),
                                       hjust = 0.5, margin = margin(b = 10)),
      plot.caption      = element_text(colour = COL_GREY, size = rel(0.72),
                                       hjust = 0),
      legend.title      = element_blank(),
      legend.text       = element_text(colour = COL_GREY, size = rel(0.85)),
      legend.position   = "top",
      legend.justification = "right",
      plot.margin       = margin(12, 16, 10, 12)
    )
}

# ------------------------------------------------------------------ 工具
# 统一保存：幻灯片用 16:9 画布，dpi 200，白底。
# 优先 ragg::agg_png（基于 systemfonts，CJK 字形自动回退，中文不会变豆腐块）
save_fig <- function(p, filename, width = 12.6, height = 4.4, dpi = 200) {
  path <- file.path(FIGDIR, filename)
  has_ragg <- requireNamespace("ragg", quietly = TRUE)
  dev <- if (has_ragg) ragg::agg_png else grDevices::png
  args <- list(filename = path, width = width, height = height,
               units = "in", res = dpi, background = "white")
  if (!has_ragg) args$res <- NULL  # png() 用 dpi 参数名不同，干脆走默认
  do.call(dev, args)
  print(p)
  grDevices::dev.off()
  cat(sprintf("  -> figures/%s  (%.1f x %.1f in, %s)\n", filename, width, height,
              if (has_ragg) "ragg" else "png"))
  invisible(path)
}

# 读 CSV（utf-8-sig 的 BOM 由 readr 自动处理，但显式指定更稳）
read_data <- function(name) {
  read_csv(file.path(DATA, name), show_col_types = FALSE,
           locale = locale(encoding = "UTF-8"))
}

# 平台因子化（保证图例顺序稳定）
as_platform <- function(x) factor(x, levels = PLAT_LEVELS)
