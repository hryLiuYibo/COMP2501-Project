#' convert_ncm_to_mp3.R
#' ====================
#'
#' Batch-convert NetEase .ncm encrypted files to .mp3 using a CLI backend.
#'
#' Strategy
#' --------
#' NetEase's `.ncm` containers wrap an mp3 stream with a header that requires
#' a custom decoder. We ship NO decoder of our own — instead we call one of
#' these CLI tools from R via `system2`:
#'
#'   * `ncmdump`    — Go single-binary, fastest (https://github.com/anonymous5l/ncmdump)
#'   * `ncmdump-py` — Python wrapper, slower but trivial to install (`pip install ncmdump-py`)
#'
#' The choice is encapsulated behind `NcmdumpConverter` (R6-ish S4-style) so
#' swapping the backend is a one-line change.
#'
#' The previous design considered a GUI drag-and-drop tool (`Trans.exe`,
#' formerly `Ncm转mp3拖一拖.exe`). That tool is dropped because it accepts no
#' command-line arguments and cannot be invoked from a script.
#'
#' Usage
#' -----
#'   Rscript R/convert_ncm_to_mp3.R --src data/ncm --dst data/mp3
#'   Rscript R/convert_ncm_to_mp3.R --src data/ncm --dst data/mp3 --exe "C:/tools/ncmdump.exe"
#'   Rscript R/convert_ncm_to_mp3.R --src data/ncm --dst data/mp3 --backend ncmdump-py
#'
#' A skip-on-existing-output rule makes the script resumable: re-running it
#' only processes files that are not yet converted.

suppressPackageStartupMessages({
  library(jsonlite)
})

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_msg <- function(level, ...) {
  ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  msg <- paste0(..., collapse = "")
  cat(sprintf("[%s] %s %s\n", ts, level, msg))
}
log_info <- function(...) log_msg("INFO ", ...)
log_warn <- function(...) log_msg("WARN ", ...)
log_err  <- function(...) log_msg("ERROR", ...)

# ---------------------------------------------------------------------------
# Converter interface
# ---------------------------------------------------------------------------

#' Abstract base. Concrete subclasses implement `convert_one()`.
setClass("NcmConverter", slots = list(name = "character"))

setGeneric("convert_one", function(converter, ncm_path, mp3_path) standardGeneric("convert_one"))
setGeneric("convert_many", function(converter, jobs, sleep = 0) standardGeneric("convert_many"))

setMethod("convert_many", signature(converter = "NcmConverter"),
  function(converter, jobs, sleep = 0) {
    ok <- 0L; fail <- 0L; failed <- character(0)
    for (j in seq_along(jobs)) {
      pair <- jobs[[j]]
      tryCatch({
        convert_one(converter, pair$ncm, pair$mp3)
        ok <- ok + 1L
      }, error = function(e) {
        fail <<- fail + 1L
        failed <<- c(failed, basename(pair$ncm))
        log_warn("convert failed: ", basename(pair$ncm), " — ", conditionMessage(e))
      })
      if (sleep > 0 && j < length(jobs)) Sys.sleep(sleep)
    }
    list(ok = ok, fail = fail, failed = failed)
  }
)

# ---------------------------------------------------------------------------
# Backend: ncmdump (Go binary)
# ---------------------------------------------------------------------------

setClass("NcmdumpCliConverter",
         contains = "NcmConverter",
         slots    = list(exe_path = "character"))

setMethod("initialize", "NcmdumpCliConverter",
  function(.Object, exe_path = "ncmdump", ...) {
    .Object@name <- "ncmdump"
    .Object@exe_path <- normalizePath(exe_path, mustWork = FALSE)
    if (!file.exists(.Object@exe_path)) {
      stop(sprintf(
        "ncmdump executable not found at: %s\nDownload from https://github.com/anonymous5l/ncmdump/releases",
        .Object@exe_path
      ))
    }
    .Object
  }
)

setMethod("convert_one", signature(converter = "NcmdumpCliConverter"),
  function(converter, ncm_path, mp3_path) {
    dir.create(dirname(mp3_path), recursive = TRUE, showWarnings = FALSE)
    tmp_dir <- file.path(dirname(mp3_path), "_tmp_ncmdump")
    dir.create(tmp_dir, showWarnings = FALSE, recursive = TRUE)
    cleanup <- function() {
      # Remove leftover mp3 + bat files. Use Sys.glob, not list.files:
      # on Windows + R 4.6.x list.files drops files containing a comma.
      leftovers <- c(Sys.glob(file.path(tmp_dir, "*.mp3")),
                     Sys.glob(file.path(tmp_dir, "*.bat")))
      for (lf in leftovers) {
        try(file.remove(lf), silent = TRUE)
      }
      if (dir.exists(tmp_dir)) try(unlink(tmp_dir, recursive = FALSE), silent = TRUE)
    }
    on.exit(cleanup, add = TRUE)

    # ncmdump (taurusxin/ncmdump 1.5.x) uses cxxopts, which is sensitive to
    # argument order: file arguments MUST come before the -o flag. We shQuote()
    # the paths so that spaces / commas survive the shell. We deliberately do
    # NOT add a `--` separator because cxxopts in this version treats `--`
    # itself as a positional argument (file).
    #
    # Encoding workaround: on Chinese Windows, R's `system2()` chokes on
    # non-ASCII file names ("unable to translate ... to native encoding").
    # The cleanest workaround is to write a one-line .bat shim that contains
    # the command in the OEM/ANSI codepage Windows expects. Encoding the bat
    # file in the system native codepage lets cmd.exe parse it correctly.
    bat_path <- tempfile(pattern = "ncmdump_", tmpdir = tmp_dir, fileext = ".bat")
    # Resolve to absolute Windows paths
    ncm_abs  <- normalizePath(ncm_path, mustWork = TRUE)
    tmp_abs  <- normalizePath(tmp_dir,  mustWork = TRUE)
    # Encode the .bat file using the system native codepage so cmd.exe
    # parses Chinese filenames. Sys.getlocale() returns the R-level locale;
    # the Windows ANSI codepage is usually "native.enc" on R 4.x.
    native_enc <- "native.enc"
    cmd_line <- sprintf('"%s" "%s" -o "%s"\r\n',
                        normalizePath(converter@exe_path, mustWork = TRUE),
                        ncm_abs, tmp_abs)
    con <- file(bat_path, open = "wb", encoding = native_enc)
    on.exit(try(close(con), silent = TRUE), add = TRUE)
    writeBin(charToRaw(enc2utf8(cmd_line)), con)   # write as raw bytes
    close(con)
    on.exit()  # we've closed the file explicitly

    # Now invoke cmd.exe on the bat file. We use shell() (not system2) so the
    # command itself stays in pure ASCII.
    bat_abs <- normalizePath(bat_path, mustWork = TRUE)
    out <- shell(sprintf('cmd.exe /c ""%s""', bat_abs), intern = TRUE, mustWork = FALSE)
    code <- attr(out, "status")
    if (is.null(code)) code <- 0L
    if (code != 0L) {
      stop(sprintf("ncmdump rc=%d: %s", code, paste(out, collapse=" | ")))
    }
    produced <- file.path(tmp_dir, paste0(tools::file_path_sans_ext(basename(ncm_path)), ".mp3"))
    if (!file.exists(produced)) {
      # Try Sys.glob as a fallback for case sensitivity or codepage issues
      cands <- Sys.glob(file.path(tmp_dir, "*.mp3"))
      if (length(cands) == 1L) {
        produced <- cands[1]
      } else {
        stop("ncmdump succeeded but expected mp3 not found: ", produced)
      }
    }
    file.rename(produced, mp3_path)
  }
)

# ---------------------------------------------------------------------------
# Backend: ncmdump-py (Python wrapper)
# ---------------------------------------------------------------------------

setClass("NcmdumpPyConverter", contains = "NcmConverter")

setMethod("initialize", "NcmdumpPyConverter",
  function(.Object, ...) {
    .Object@name <- "ncmdump-py"
    # We don't hard-fail here; the actual call will surface the ImportError.
    .Object
  }
)

setMethod("convert_one", signature(converter = "NcmdumpPyConverter"),
  function(converter, ncm_path, mp3_path) {
    dir.create(dirname(mp3_path), recursive = TRUE, showWarnings = FALSE)
    # Invoke a tiny inline Python script. Avoids us having to ship a separate .py file.
    py <- Sys.which("python")
    if (!nzchar(py)) py <- Sys.which("python3")
    if (!nzchar(py)) stop("no python interpreter found on PATH (ncmdump-py backend)")
    script <- sprintf(
      "from ncmdump import dump\ndump(%s, %s)\n",
      shQuote(ncm_path), shQuote(mp3_path)
    )
    out <- system2(py, args = c("-c", shQuote(script)), stdout = TRUE, stderr = TRUE)
    code <- attr(out, "status")
    if (is.null(code)) code <- 0L
    if (code != 0L) {
      stop(sprintf("ncmdump-py failed: %s", paste(out, collapse=" | ")))
    }
  }
)

# ---------------------------------------------------------------------------
# Job collection
# ---------------------------------------------------------------------------

collect_jobs <- function(src_dir, dst_dir) {
  if (!dir.exists(src_dir)) {
    log_warn("src dir does not exist: ", src_dir)
    return(list())
  }
  # Use Sys.glob, NOT list.files(pattern=...): on Windows + R 4.6.x the latter
  # silently drops files whose names contain a comma (e.g. "Gorillaz,De La Soul").
  ncm_files <- Sys.glob(file.path(src_dir, "*.ncm"))
  jobs <- list()
  for (ncm in ncm_files) {
    base <- tools::file_path_sans_ext(basename(ncm))
    mp3  <- file.path(dst_dir, paste0(base, ".mp3"))
    if (file.exists(mp3)) {
      log_info("skip existing: ", basename(mp3))
      next
    }
    jobs[[length(jobs) + 1L]] <- list(ncm = ncm, mp3 = mp3)
  }
  jobs
}

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

main <- function(argv = NULL) {
  if (is.null(argv)) argv <- commandArgs(trailingOnly = TRUE)

  parse_args <- function(a) {
    out <- list(src = NULL, dst = NULL, backend = "ncmdump", exe = "ncmdump", sleep = 0)
    i <- 1L
    while (i <= length(a)) {
      x <- a[[i]]
      if (x %in% c("--src", "-s")) {
        out$src <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--dst", "-d")) {
        out$dst <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--backend") {
        out$backend <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--exe") {
        out$exe <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--sleep") {
        out$sleep <- as.numeric(a[[i + 1L]]); i <- i + 2L
      } else if (x %in% c("--help", "-h")) {
        cat("usage: Rscript convert_ncm_to_mp3.R --src DIR --dst DIR [--backend ncmdump|ncmdump-py] [--exe PATH] [--sleep SEC]\n")
        quit(status = 0L)
      } else {
        stop("unknown arg: ", x)
      }
    }
    out
  }
  args <- parse_args(argv)
  if (is.null(args$src) || is.null(args$dst)) {
    stop("--src and --dst are required")
  }

  converter <- switch(args$backend,
    "ncmdump"    = new("NcmdumpCliConverter", exe_path = args$exe),
    "ncmdump-py" = new("NcmdumpPyConverter"),
    stop("unknown backend: ", args$backend)
  )

  jobs <- collect_jobs(args$src, args$dst)
  log_info("backend=", converter@name, " jobs=", length(jobs),
           " src=", args$src, " dst=", args$dst)

  if (length(jobs) == 0L) {
    log_info("nothing to do")
    return(invisible(0L))
  }
  res <- convert_many(converter, jobs, sleep = args$sleep)
  log_info("done ok=", res$ok, " fail=", res$fail)
  if (res$fail > 0L) {
    log_warn("failed files (first 5): ", paste(head(res$failed, 5), collapse = ", "))
  }
  invisible(if (res$fail == 0L) 0L else 1L)
}

if (!interactive() && identical(sys.nframe(), 0L)) {
  tryCatch(main(), error = function(e) {
    log_err("fatal: ", conditionMessage(e))
    quit(status = 1L)
  })
}
