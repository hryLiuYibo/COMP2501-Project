#' import_personal_excel.R
#' =====================
#'
#' Read the user's personal NetEase Cloud Music export (manually built from
#' the web UI) and convert it into the project's standard
#' `data/songs_catalog.json`.
#'
#' Background
#' ----------
#' The original project plan was to scrape NetEase's official weekly
#' hot-song chart for 2020-2025. That approach is impossible because
#' NetEase does not publish a weekly archive; the toplist page only ever
#' shows the live chart at the moment of query. See DESIGN.md for the
#' full discussion.
#'
#' After pivoting, the project now analyses the user's own listening
#' history. The user exports a small spreadsheet by hand from the NetEase
#' web UI (or copies the relevant fields out of their account page).
#' The spreadsheet is the source of truth; this script is the bridge
#' into the analysis pipeline.
#'
#' Expected spreadsheet columns
#' ----------------------------
#'   song_name    - character
#'   artist       - character, possibly NA
#'   song_id      - numeric or character, NetEase 64-bit id (10-digit)
#'   first_played - date, any reasonable format ("2022-03-15",
#'                  "2022/03/15", "Mar 15 2022", Excel serial date, ...).
#'                  Some rows may be NA (songs added before logging
#'                  started).
#'   play_count   - integer; may be NA
#'
#' Multi-artist encoding
#' ---------------------
#' The `artist` column sometimes lists several artists joined with "&"
#' or "/" or "、". We split on any of these so each catalog entry has
#' a proper `artists` array.
#'
#' Output
#' ------
#'   data/songs_catalog.json
#'     "<song_id>": {
#'       "song_id":     "...",
#'       "name":        "...",
#'       "artists":     [...],
#'       "first_played": "YYYY-MM-DD" or null,
#'       "play_count":   N or null,
#'       "mp3_file":    "<song_id>.mp3"   # we will only have this once
#'                                         # the user supplies matching mp3s
#'     }
#'
#' Also writes a tidy CSV alongside the JSON for quick viewing in Excel:
#'   data/personal_history.csv
#'
#' Usage
#' -----
#'   Rscript R/import_personal_excel.R --csv path/to/export.csv --out data
#'
#'   # The CSV must have the five columns above (case insensitive, in any
#'   # order). Missing values may be empty cells, "NA", or "N/A".

suppressPackageStartupMessages({
  if (!requireNamespace("readr",  quietly = TRUE)) stop("readr is required")
  if (!requireNamespace("jsonlite",quietly = TRUE)) stop("jsonlite is required")
  library(readr)
  library(jsonlite)
})

log_msg <- function(level, ...) {
  ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(sprintf("[%s] %s %s\n", ts, level, paste0(..., collapse="")))
}
log_info <- function(...) log_msg("INFO ", ...)
log_warn <- function(...) log_msg("WARN ", ...)
log_err  <- function(...) log_msg("ERROR", ...)

# ---------------------------------------------------------------------------
# Column detection (case-insensitive, accept a few common aliases)
# ---------------------------------------------------------------------------

#' Given the column names of an input data.frame, return a named list of
#' the canonical fields we care about. Each value is the *actual* column
#' name found (or NULL if missing).
match_columns <- function(cols) {
  canon <- list(
    song_name    = c("song_name", "name", "title", "song"),
    artist       = c("artist", "artists", "singer"),
    song_id      = c("song_id", "id", "netease_id"),
    first_played = c("first_played", "first_heard", "first_listen",
                     "first_play", "date_added", "added_at", "date",
                     "first_played_at"),
    play_count   = c("play_count", "plays", "listens", "count")
  )
  out <- list()
  for (field in names(canon)) {
    hit <- intersect(tolower(cols), canon[[field]])
    if (length(hit) == 0L) {
      out[[field]] <- NULL
    } else {
      # Use the original-cased version of the matched name
      out[[field]] <- cols[tolower(cols) == hit[1L]][1L]
    }
  }
  out
}

# ---------------------------------------------------------------------------
# Artist splitter
# ---------------------------------------------------------------------------

#' Split a multi-artist string into a character vector.
#' Recognised separators: " & ", " / ", "、", "，", " feat. ", " ft. "
#' and their no-space variants. Returns character(0) on NA / blank.
split_artists <- function(s) {
  if (is.na(s) || !nzchar(s)) return(character(0))
  # Normalise "feat." / "ft." with optional spaces into a single comma.
  s <- gsub("\\s*(feat\\.?|ft\\.?)\\s*", ",", s, perl = TRUE, ignore.case = TRUE)
  # ASCII-style separators (",", "&", "/")
  s <- gsub("[,&/]+", ",", s)
  # CJK separators: "、" (U+3001) and "，" (U+FF0C). Encoded as bytes so we
  # don't have to depend on locale settings.
  s <- gsub("\xe3\x80\x81", ",", s, useBytes = TRUE)
  s <- gsub("\xef\xbc\x8c", ",", s, useBytes = TRUE)
  parts <- strsplit(s, ",", fixed = TRUE)[[1]]
  parts <- trimws(parts)
  parts[nzchar(parts)]
}

#' Detect the delimiter used in a small slice of the file. We test ",", ";"
#' and tab, then pick whichever has the highest consistent count in the
#' first few non-empty lines.
detect_delim <- function(path) {
  lines <- readLines(path, n = 5, warn = FALSE, encoding = "UTF-8")
  lines <- lines[nzchar(lines)]
  if (length(lines) == 0L) stop("CSV file is empty")
  counts <- c(
    ","  = max(vapply(lines, function(s) lengths(regmatches(s, gregexpr(",",  s, fixed = TRUE))), integer(1))),
    ";"  = max(vapply(lines, function(s) lengths(regmatches(s, gregexpr(";",  s, fixed = TRUE))), integer(1))),
    "\t" = max(vapply(lines, function(s) lengths(regmatches(s, gregexpr("\t", s, fixed = TRUE))), integer(1)))
  )
  if (max(counts) == 0L) stop("no delimiter detected (tried ',', ';', '\\t')")
  delim <- names(which.max(counts))
  log_info("detected delimiter: '", delim, "' (counts: ",
           paste(sprintf("%s=%d", names(counts), counts), collapse=", "), ")")
  delim
}

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

#' Coerce a value to "YYYY-MM-DD" or NA. Accepts:
#'   * ISO-ish character ("2022-03-15", "2022/3/15", "2022.3.15")
#'   * "Mar 15 2022" / "15 Mar 2022"
#'   * Excel serial date number (e.g. 44673) — origin 1899-12-30
parse_first_played <- function(x) {
  if (is.na(x)) return(NA_character_)
  if (is.numeric(x)) {
    # Excel serial date. 1899-12-30 is the modern Excel origin (handles the
    # 1900 leap-year bug consistently).
    d <- as.Date(x, origin = "1899-12-30")
    return(format(d, "%Y-%m-%d"))
  }
  s <- as.character(x)
  s <- trimws(s)
  if (!nzchar(s) || toupper(s) %in% c("NA", "N/A", "NULL", "NONE", "-")) {
    return(NA_character_)
  }
  # Normalise common separators ("/", ".") to "-" so that a single date
  # grammar accepts more spellings.
  s_norm <- gsub("[/.]", "-", s)
  # Try base R's parser first (handles "YYYY-MM-DD" cleanly).
  out <- tryCatch({
    d <- as.Date(s_norm)
    if (!is.na(d)) format(d, "%Y-%m-%d") else NA_character_
  }, error = function(e) NA_character_)
  if (!is.na(out)) return(out)

  # Fall back to readr's flexible parser. We list a wide set of plausible
  # orderings; the first one that matches wins.
  out <- tryCatch({
    d <- readr::parse_date_time(
      s_norm,
      orders = c("Y-m-d", "Y/m/d", "Y.m.d",
                 "d-m-Y", "d/m/Y", "d.m.Y",
                 "m/d/Y", "Ymd", "d-b-Y", "b-d-Y"),
      quiet = TRUE
    )
    if (length(d) == 1L && !is.na(d)) format(as.Date(d), "%Y-%m-%d") else NA_character_
  }, error = function(e) NA_character_)
  out
}

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

load_export <- function(csv_path) {
  if (!file.exists(csv_path)) {
    stop("CSV not found: ", csv_path)
  }
  log_info("reading ", csv_path)
  delim <- detect_delim(csv_path)
  df <- readr::read_delim(
    csv_path,
    delim = delim,
    col_types = readr::cols(.default = readr::col_character()),
    show_col_types = FALSE,
    progress = FALSE,
    locale = readr::locale(encoding = "UTF-8")
  )
  log_info("read ", nrow(df), " rows, ", ncol(df), " columns: ", paste(names(df), collapse=", "))

  mapping <- match_columns(names(df))
  missing_req <- setdiff(c("song_name", "song_id"), names(mapping[mapping != ""]))
  # Filter out NULLs from mapping first
  mapping <- Filter(Negate(is.null), mapping)
  if (length(missing_req) > 0L) {
    stop("required column(s) missing in CSV: ", paste(missing_req, collapse=", "),
         "\nfound columns: ", paste(names(df), collapse=", "))
  }
  if (is.null(mapping$artist))       log_warn("no 'artist' column found; artists will be empty")
  if (is.null(mapping$first_played)) log_warn("no 'first_played' column found; dates will be NA")
  if (is.null(mapping$play_count))   log_warn("no 'play_count' column found; counts will be NA")

  # Build tidy frame
  out <- data.frame(
    song_id      = trimws(df[[mapping$song_id]]),
    song_name    = trimws(df[[mapping$song_name]]),
    stringsAsFactors = FALSE
  )
  if (!is.null(mapping$artist)) {
    out$artist_raw <- trimws(df[[mapping$artist]])
  } else {
    out$artist_raw <- NA_character_
  }
  if (!is.null(mapping$first_played)) {
    out$first_played <- vapply(df[[mapping$first_played]], parse_first_played, character(1))
  } else {
    out$first_played <- NA_character_
  }
  if (!is.null(mapping$play_count)) {
    pc <- suppressWarnings(as.integer(df[[mapping$play_count]]))
    out$play_count <- pc
  } else {
    out$play_count <- NA_integer_
  }

  # Drop rows with empty song_id (can't be a catalog key)
  n_total <- nrow(out)
  out <- out[!is.na(out$song_id) & nzchar(out$song_id), , drop = FALSE]
  if (nrow(out) < n_total) {
    log_warn("dropped ", n_total - nrow(out), " rows with empty song_id")
  }

  # Normalise song_id to character (NetEase ids can exceed 32-bit int)
  out$song_id <- format(as.numeric(out$song_id), scientific = FALSE, trim = TRUE)

  out
}

# ---------------------------------------------------------------------------
# Catalog writer
# ---------------------------------------------------------------------------

build_catalog_from_export <- function(df) {
  cat <- list()
  for (i in seq_len(nrow(df))) {
    r <- df[i, ]
    art_vec <- split_artists(r$artist_raw)
    # We always include the four core fields. The optional play_count /
    # first_played are emitted as JSON `null` when missing — that keeps
    # downstream code simple (`entry$play_count %||% 0`) and the schema
    # uniform across rows.
    entry <- list(
      song_id      = r$song_id,
      name         = r$song_name,
      artists      = as.list(art_vec),
      mp3_file     = paste0(r$song_id, ".mp3"),
      play_count   = if (is.na(r$play_count))   NULL else as.integer(r$play_count),
      first_played = if (is.na(r$first_played)) NULL else r$first_played
    )
    cat[[r$song_id]] <- entry
  }
  cat
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

main <- function(argv = NULL) {
  if (is.null(argv)) argv <- commandArgs(trailingOnly = TRUE)
  parse_args <- function(a) {
    out <- list(csv = NULL, out = "data", catalog = "data/songs_catalog.json",
                history_csv = "data/personal_history.csv")
    i <- 1L
    while (i <= length(a)) {
      x <- a[[i]]
      if (x == "--csv") { out$csv <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--out","-o")) { out$out <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--catalog") { out$catalog <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--history") { out$history_csv <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--help","-h")) {
        cat("usage: Rscript import_personal_excel.R --csv FILE --out DIR [--catalog PATH] [--history PATH]\n")
        quit(status = 0L)
      } else { stop("unknown arg: ", x) }
    }
    out
  }
  args <- parse_args(argv)
  if (is.null(args$csv)) stop("--csv is required")
  dir.create(args$out, recursive = TRUE, showWarnings = FALSE)

  df <- load_export(args$csv)
  log_info("parsed ", nrow(df), " songs")

  cat_obj <- build_catalog_from_export(df)
  # jsonlite has a subtle distinction between `NA` and `NULL`:
  #   NA_integer_ -> "null" with na="null"
  #   NULL        -> {} with default settings
  # We want JSON `null` for any missing value. Easiest: convert all NA's
  # to NULL before serialising, then use null="null" to render them.
  fix_na <- function(x) {
    if (is.list(x)) lapply(x, fix_na)
    else if (length(x) == 1L && is.atomic(x) && is.na(x)) NULL
    else x
  }
  cat_obj <- fix_na(cat_obj)
  json <- toJSON(
    cat_obj,
    pretty     = TRUE,
    auto_unbox = TRUE,
    force      = TRUE,
    null       = "null"
  )
  writeLines(json, con = args$catalog, useBytes = TRUE)
  log_info("wrote catalog ", args$catalog, " (", length(cat_obj), " entries)")

  # Tidy CSV side-output for easy viewing
  history <- data.frame(
    song_id      = df$song_id,
    song_name    = df$song_name,
    artist       = df$artist_raw,
    first_played = df$first_played,
    play_count   = df$play_count,
    stringsAsFactors = FALSE
  )
  readr::write_csv(history, args$history_csv)
  log_info("wrote history ", args$history_csv)
  invisible(0L)
}

if (!interactive() && identical(sys.nframe(), 0L)) {
  tryCatch(main(), error = function(e) {
    log_err("fatal: ", conditionMessage(e))
    quit(status = 1L)
  })
}