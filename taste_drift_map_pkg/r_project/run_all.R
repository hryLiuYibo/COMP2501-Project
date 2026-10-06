# =============================================================================
# run_all.R — regenerate every figure in one command
# -----------------------------------------------------------------------------
# Usage:   Rscript run_all.R          (from anywhere)
# Needs:   ggplot2, dplyr, readr, tidyr, scales, patchwork  (ragg recommended)
#
# Figures are written to the repository root's figures/ directory.
# =============================================================================

scripts <- c(
  "01_map_overview.R",
  "02_map_platform.R",
  "03_map_trajectory.R",
  "04_map_monthly.R",
  "05_map_coverage.R",
  "06_chain_waveform.R",
  "07_chain_spectrogram.R",
  "08_chain_vector.R",
  "09_chain_similarity.R"
)

# --- locate THIS file's directory -------------------------------------------
# `--file=` only reflects the *entry* script, which is not necessarily this one
# (e.g. when run_all.R is itself used as a driver from elsewhere). So we also
# look for the directory that actually contains these figure scripts.
.this_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE)
  f <- sub("^--file=", "", a[grep("^--file=", a)])
  d <- if (length(f)) dirname(normalizePath(f[1])) else getwd()

  # if the entry script isn't here, walk up / down looking for our scripts
  if (file.exists(file.path(d, "09_chain_similarity.R"))) return(d)
  if (file.exists(file.path(d, "r_project", "09_chain_similarity.R"))) {
    return(file.path(d, "r_project"))
  }
  up <- normalizePath(file.path(d, ".."), mustWork = FALSE)
  if (file.exists(file.path(up, "09_chain_similarity.R"))) return(up)
  d   # fall back; the error below will be explicit
}

setwd(.this_dir())
if (!file.exists("09_chain_similarity.R")) {
  stop("run_all.R: cannot find the figure scripts.\n",
       "  Tried working directory: ", getwd(), "\n",
       "  Run it as:  Rscript r_project/run_all.R   (from the repo root)")
}

ok <- 0L
for (s in scripts) {
  cat("\n===", s, "=============================================\n")
  res <- tryCatch({ source(s, echo = FALSE); TRUE },
                  error = function(e) { cat("ERROR:", conditionMessage(e), "\n"); FALSE })
  ok <- ok + as.integer(res)
}
cat(sprintf("\n%d/%d scripts succeeded\n", ok, length(scripts)))
if (ok < length(scripts)) quit(status = 1)
