# =============================================================================
# _common.R — sourced at the top of every figure script
# -----------------------------------------------------------------------------
# Job: locate the r_project directory -> source theme_taste.R -> define helpers,
# so the figure scripts themselves only say WHAT to draw.
#
# Two supported entry points:
#   (a) Rscript r_project/01_map_overview.R     -> --file= names the script
#   (b) Rscript r_project/run_all.R             -> source()s the scripts;
#                                                  run_all.R has already set the
#                                                  working directory to r_project/
# =============================================================================

# Locate the directory holding theme_taste.R / data/ / the 09_* marker script.
.find_rp_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE)
  f <- sub("^--file=", "", a[grep("^--file=", a)])

  cands <- character(0)
  # (b) when source()d, the calling frame knows which file is executing
  for (i in rev(seq_len(sys.nframe()))) {
    of <- tryCatch(sys.frame(i)$ofile, error = function(e) NULL)
    if (is.character(of) && length(of) == 1 && nzchar(of)) {
      cands <- c(cands, dirname(normalizePath(of, mustWork = FALSE)))
    }
  }
  # (a) direct Rscript
  if (length(f)) cands <- c(cands, dirname(normalizePath(f[1], mustWork = FALSE)))
  # last resort: wherever we were started from
  cands <- c(cands, getwd())

  marker <- "theme_taste.R"
  for (d in cands) {
    for (up in 0:2) {
      p <- if (up == 0) d else normalizePath(file.path(d, strrep("../", up)), mustWork = FALSE)
      if (file.exists(file.path(p, marker))) return(p)
    }
  }
  stop("_common.R: cannot locate ", marker, ".\n",
       "  Candidates tried:\n    ", paste(unique(cands), collapse = "\n    "), "\n",
       "  Run from the repo root:  Rscript r_project/run_all.R")
}

RP_DIR <- .find_rp_dir()
source(file.path(RP_DIR, "theme_taste.R"))

`%||%` <- function(a, b) if (is.null(a)) b else a
