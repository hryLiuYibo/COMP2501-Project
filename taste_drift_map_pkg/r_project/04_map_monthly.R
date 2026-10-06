# =============================================================================
# 04_map_monthly.R — 把粒度切到月：波动是常态，趋势不存在（QQ 月榜独有）
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

md <- read_data("monthly_drift.csv") |>
  filter(platform == "QQ Music") |>
  mutate(i = row_number(), year = as.integer(year))

first_year <- min(md$year)
year_starts <- md |> group_by(year) |> summarise(i = min(i))

p <- ggplot(md, aes(i, angle_to_first_deg)) +
  # 年份分隔线 + 年份标签
  geom_vline(data = year_starts, aes(xintercept = i),
             colour = COL_GRID, linetype = "dashed", linewidth = 0.45) +
  geom_text(data = year_starts, aes(x = i + 0.3, y = 25.2, label = year),
            colour = COL_GREY, size = 3.1, hjust = 0, inherit.aes = FALSE) +
  geom_line(colour = COL_QQ, linewidth = 0.5, alpha = 0.85) +
  geom_point(colour = COL_QQ, size = 1.15, alpha = 0.9) +
  # 年度质心（该年第一个月的夹角处画星标）
  geom_point(data = year_starts, aes(x = i, y = 11),
             shape = 8, size = 3.6, colour = COL_DARK, inherit.aes = FALSE) +
  annotate("text", x = 66.5, y = 11, label = "= yearly centroid",
           size = 2.9, colour = COL_DARK, hjust = 0) +
  annotate("text", x = 1, y = 22.8, size = 3.6, fontface = "bold", colour = COL_QQ,
           hjust = 0, label = "months swing 8-23.5\u00b0") +
  annotate("text", x = 1, y = 13.3, size = 3.0, colour = COL_GREY, hjust = 0,
           label = "yearly centroids (stars) stay near 10\u00b0") +
  scale_x_continuous(breaks = seq(0, 70, 10)) +
  scale_y_continuous(limits = c(0, 26.5), expand = expansion(mult = c(0, 0))) +
  labs(
    title = "Monthly granularity: month-to-month jumps of 8-23.5\u00b0; the yearly drift (stars) is drowned out",
    subtitle = "Angle of each month's centroid to the 2018-08 centroid - playlists keep rotating, the mix of styles does not",
    x = "QQ Music monthly chart issue (2018.08 - 2024.12)",
    y = "Angle to 2018-08 centroid (degrees)"
  ) +
  theme_taste() +
  theme(panel.grid.major.x = element_blank())

save_fig(p, "map_monthly.png", width = 13.0, height = 4.55)
