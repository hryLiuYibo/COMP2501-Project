#' fetch_weekly_top100.R
#' ====================
#'
#' Fetch NetEase Cloud Music "hot song" weekly chart and dump to JSON.
#'
#' Strategy
#' --------
#' The NetEase toplist page (https://music.163.com/discover/toplist?id=3778678)
#' is server-side rendered. The current top 200 songs are embedded as a single
#' JSON array inside the first `<textarea>` node of the document. We pull that
#' JSON directly with `httr` (no headless browser) and decode it with
#' `jsonlite`.
#'
#' We do NOT call NetEase's signed JSON APIs (`/api/v3/...`), because the
#' signature scheme is undocumented and reverse-engineered in third-party
#' projects (e.g. NeteaseCloudMusicApi). That approach is fragile and legally
#' grey. The public toplist page is the path of least resistance and least risk.
#'
#' Output
#' ------
#' `data/raw/weekly_top100/<YYYY-Www>.json`
#'
#' ```json
#' {
#'   "week":       "2025-W38",
#'   "snapshot_time": "2026-09-21T20:00:00+08:00",
#'   "platform":   "netease",
#'   "chart_id":   3778678,
#'   "n_songs":    200,
#'   "songs": [
#'     {"rank":1, "song_id":..., "name":"...", "artists":["..."], "duration_ms":...},
#'     ...
#'   ]
#' }
#' ```
#'
#' Usage
#' -----
#'   Rscript R/fetch_weekly_top100.R --week 2025-W38 --top 100 --out data/raw/weekly_top100
#'   Rscript R/fetch_weekly_top100.R --week 2025-W38 --top 200 --out data/raw/weekly_top100
#'   Rscript R/fetch_weekly_top100.R --week "auto" --top 200 --out data/raw/weekly_top100
#'     # "auto" picks the current ISO week
#'
#' Note on "weekly" cadence
#' ------------------------
#' NetEase does NOT publish historical weekly snapshots. There is no archive
#' endpoint. The single live toplist at the moment we query is the only thing
#' we can capture. To build a historical series we re-poll on different days
#' and treat each poll as one snapshot. The `week` argument above names the
#' *target* week (e.g. ISO week of the poll date), not a real NetEase week.
#' See DESIGN.md §3.1 for the schema note on this distinction.

suppressPackageStartupMessages({
  library(httr)
  library(jsonlite)
  library(rvest)
})

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NETEASE_HOT_TOP_URL  <- "https://music.163.com/discover/toplist"
NETEASE_HOT_TOP_ID   <- 3778678L

USER_AGENT <- paste0(
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ",
  "AppleWebKit/537.36 (KHTML, like Gecko) ",
  "Chrome/120.0.0.0 Safari/537.36"
)

# Anti-scraping throttle. Conservative default: 2-5s per request.
REQUEST_SLEEP_RANGE <- c(2.0, 5.0)
MAX_RETRIES         <- 3
RETRY_BACKOFF       <- 5   # exponential backoff base, seconds

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_msg <- function(level, ...) {
  ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  msg <- paste0(..., collapse = "")
  cat(sprintf("[%s] %s %s\n", ts, level, msg))
}
log_info  <- function(...) log_msg("INFO ", ...)
log_warn  <- function(...) log_msg("WARN ", ...)
log_error <- function(...) log_msg("ERROR", ...)

# ---------------------------------------------------------------------------
# Week label helpers (ISO week, format "YYYY-Www")
# ---------------------------------------------------------------------------

#' Build an ISO week label from a Date.
#' Examples: 2020-01-01 -> "2020-W01", 2025-12-31 -> "2026-W01"
iso_week_label <- function(d) {
  stopifnot(inherits(d, "Date"))
  iso <- as.integer(format(d, "%G"))   # ISO year
  wk  <- as.integer(format(d, "%V"))   # ISO week
  sprintf("%d-W%02d", iso, wk)
}

#' Parse "YYYY-Www" into a Date (Monday of that ISO week).
parse_week_label <- function(s) {
  m <- regmatches(s, regexec("^([0-9]{4})-W([0-9]{2})$", s))[[1]]
  if (length(m) != 3) {
    stop(sprintf("invalid week label: '%s' (expected YYYY-Www)", s))
  }
  yr <- as.integer(m[2]); wk <- as.integer(m[3])
  # Monday of ISO week: 4 Jan is always in week 1; (4 - weekday(4 Jan)) gives Monday of week 1.
  jan4   <- as.Date(sprintf("%04d-01-04", yr))
  monday1 <- jan4 - as.integer(format(jan4, "%w")) + 1L
  monday1 + 7L * (wk - 1L)
}

# ---------------------------------------------------------------------------
# Network layer
# ---------------------------------------------------------------------------

#' Fetch the live hot-song toplist page once. Returns parsed HTML doc.
fetch_toplist_page <- function() {
  last_err <- NULL
  for (attempt in seq_len(MAX_RETRIES)) {
    r <- tryCatch(
      GET(
        NETEASE_HOT_TOP_URL,
        query = list(id = NETEASE_HOT_TOP_ID),
        add_headers(`User-Agent` = USER_AGENT,
                    `Referer`    = "https://music.163.com/",
                    `Accept`     = "text/html,application/xhtml+xml"),
        timeout(20)
      ),
      error = function(e) e
    )
    if (inherits(r, "error")) {
      last_err <- r
      log_warn("HTTP error (attempt ", attempt, "/", MAX_RETRIES, "): ", conditionMessage(r))
      Sys.sleep(RETRY_BACKOFF * (2 ^ (attempt - 1)))
      next
    }
    if (status_code(r) != 200) {
      last_err <- sprintf("HTTP %d", status_code(r))
      log_warn(last_err, " (attempt ", attempt, "/", MAX_RETRIES, ")")
      Sys.sleep(RETRY_BACKOFF * (2 ^ (attempt - 1)))
      next
    }
    return(content(r, as = "text", encoding = "UTF-8"))
  }
  stop(sprintf("fetch_toplist_page failed after %d attempts: %s",
               MAX_RETRIES, conditionMessage(last_err)))
}

#' Locate the songs JSON in the raw HTML and return the decoded array.
#' The toplist page carries a `<textarea id="song-list-pre-data">` whose text
#' is a JSON array of song objects. We target that node by id (rvest) when
#' available; we fall back to a regex search if rvest fails.
extract_songs_json <- function(html_text) {
  raw <- NULL

  # Preferred path: parse with rvest and locate the textarea by id.
  if (requireNamespace("rvest", quietly = TRUE)) {
    node <- tryCatch(
      rvest::html_node(rvest::read_html(html_text), "#song-list-pre-data"),
      error = function(e) NULL
    )
    if (!is.null(node)) {
      raw <- rvest::html_text(node)
    }
  }

  # Fallback: regex on raw HTML. The textarea contents can span newlines and
  # inline double quotes, so we use DOTALL via [\\s\\S] in PCRE mode.
  if (is.null(raw) || !nzchar(raw)) {
    m <- regmatches(
      html_text,
      gregexpr(
        "<textarea[^>]*id=\"song-list-pre-data\"[^>]*>([\\s\\S]*?)</textarea>",
        html_text, perl = TRUE
      )
    )[[1]]
    if (length(m) == 0L) {
      stop("could not find <textarea id=\"song-list-pre-data\"> on the page (NetEase may have changed layout)")
    }
    raw <- sub("<textarea[^>]*>", "", m[1])
    raw <- sub("</textarea>$", "", raw)
  }

  arr <- fromJSON(raw, simplifyVector = FALSE)
  if (!is.list(arr) || length(arr) == 0L) {
    stop("decoded songs JSON is empty or not a list")
  }
  arr
}

#' Convert one raw song object into a clean row matching our schema.
#' Returns NULL if the song lacks a usable id.
song_to_row <- function(s, rank) {
  if (is.null(s$id) || is.null(s$name)) return(NULL)
  artists <- vapply(s$artists %||% list(), function(a) a$name %||% "", character(1))
  list(
    rank        = rank,
    # NetEase ids are 64-bit, larger than R's 32-bit int max (~2.15e9).
    # jsonlite decodes them as numeric (double), so we round-trip through
    # character to preserve precision. We strip the ".0" that comes from
    # whole-number doubles.
    song_id     = format(as.numeric(s$id), scientific = FALSE, trim = TRUE),
    name        = as.character(s$name),
    artists     = as.list(artists),
    duration_ms = as.integer(s$duration %||% 0L),
    score       = if (!is.null(s$score)) as.numeric(s$score) else NA_real_
  )
}

#' `%||%` is missing from base R until 4.4. Provide a local fallback.
`%||%` <- function(a, b) if (is.null(a)) b else a

#' Pull the top N songs (1-indexed by rank) from the page.
fetch_toplist <- function(top_n = 100L) {
  html_text <- fetch_toplist_page()
  songs_raw <- extract_songs_json(html_text)
  if (length(songs_raw) < top_n) {
    log_warn("page returned only ", length(songs_raw),
             " songs; using all of them (asked for top_n=", top_n, ")")
    top_n <- length(songs_raw)
  }
  rows <- list()
  for (i in seq_len(top_n)) {
    row <- song_to_row(songs_raw[[i]], rank = i)
    if (!is.null(row)) rows[[length(rows) + 1L]] <- row
  }
  rows
}

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

save_snapshot <- function(week_label, chart_id, rows, out_dir) {
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  out_path <- file.path(out_dir, sprintf("%s.json", week_label))
  if (file.exists(out_path)) {
    log_info("snapshot exists, skipping: ", out_path)
    return(invisible(out_path))
  }
  payload <- list(
    week         = week_label,
    snapshot_time = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
    platform     = "netease",
    chart_id     = chart_id,
    n_songs      = length(rows),
    songs        = rows
  )
  json <- toJSON(payload, pretty = TRUE, auto_unbox = TRUE, force = TRUE)
  writeLines(json, con = out_path, useBytes = TRUE)
  log_info("wrote ", out_path, " (", length(rows), " songs)")
  invisible(out_path)
}

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

main <- function(argv = NULL) {
  if (is.null(argv)) argv <- commandArgs(trailingOnly = TRUE)

  parse_args <- function(a) {
    out <- list(week = NULL, top = 100L, out = "data/raw/weekly_top100")
    i <- 1L
    while (i <= length(a)) {
      x <- a[[i]]
      if (x %in% c("--week", "-w")) {
        out$week <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--top", "-n")) {
        out$top <- as.integer(a[[i + 1L]]); i <- i + 2L
      } else if (x %in% c("--out", "-o")) {
        out$out <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--help", "-h")) {
        cat("usage: Rscript fetch_weekly_top100.R --week <YYYY-Www|auto> [--top N] --out DIR\n")
        quit(status = 0L)
      } else {
        stop("unknown arg: ", x)
      }
    }
    out
  }
  args <- parse_args(argv)
  if (is.null(args$week)) stop("--week is required (use --week auto for current ISO week)")

  if (identical(args$week, "auto")) {
    week_label <- iso_week_label(Sys.Date())
  } else {
    week_label <- args$week
  }
  log_info("fetching ", args$top, " songs for week ", week_label, " -> ", args$out)

  rows <- fetch_toplist(top_n = args$top)
  log_info("parsed ", length(rows), " rows")
  path <- save_snapshot(week_label, NETEASE_HOT_TOP_ID, rows, args$out)
  log_info("done: ", path)
  invisible(0L)
}

if (!interactive() && identical(sys.nframe(), 0L)) {
  tryCatch(main(), error = function(e) {
    log_error("fatal: ", conditionMessage(e))
    quit(status = 1L)
  })
}
