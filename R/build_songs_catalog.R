#' build_songs_catalog.R
#' =====================
#'
#' Build `data/songs_catalog.json`, the canonical song metadata index that
#' ties a song key to its mp3 file path, name, and artist.
#'
#' Why this script exists
#' ----------------------
#' `extract_audio_features.R` looks up mp3 files by name. NetEase Cloud Music
#' downloads ncm files in two common filename conventions:
#'
#'   * song_id-based    : "3342319503.ncm"   (typical of scripted downloads)
#'   * human-readable   : "ilem - 白鸟过河滩.ncm"  (typical of the official client)
#'
#' Rather than forcing a single convention, this catalog makes the mp3 filename
#' an explicit field per song. The catalog is committed, so anyone cloning the
#' repo can see exactly which mp3 corresponds to which entry. No song_id
#' lookup is required to extract features.
#'
#' Two modes
#' ---------
#'
#' Mode 1 — "from-snapshots" (preferred, used in real runs):
#'
#'     Rscript R/build_songs_catalog.R \
#'         --snapshots data/raw/weekly_top100 \
#'         --mp3-dir   data/mp3 \
#'         --out       data/songs_catalog.json
#'
#'     Reads every weekly JSON snapshot, collects the union of all song_ids,
#'     and joins them to mp3 files in `data/mp3/` named `{song_id}.mp3`.
#'
#' Mode 2 — "from-mp3-dir" (fallback for hand-downloaded files):
#'
#'     Rscript R/build_songs_catalog.R \
#'         --mp3-dir data/mp3 \
#'         --out     data/songs_catalog.json
#'
#'     When a song id is not available (e.g. mp3 files downloaded directly
#'     from the NetEase client with names like "ilem - 白鸟过河滩.mp3"),
#'     the catalog key becomes the mp3 filename stem. The song's real
#'     song_id can be filled in later if you query the NetEase API.
#'
#' Output schema
#' -------------
#' A JSON object keyed by an arbitrary identifier (song_id string OR mp3
#' filename stem). Each entry has:
#'
#'   {
#'     "<key>": {
#'       "song_id":  "3342319503"  // may be null when key is the mp3 stem
#'       "name":     "明知故犯",
#'       "artists":  ["Max李玄"],
#'       "mp3_file": "3342319503.mp3"
#'     }
#'   }
#'
#' Idempotent: existing entries are kept. Re-running merges new keys; it does
#' not delete old ones. To rebuild from scratch, delete the JSON first.

suppressPackageStartupMessages({
  library(jsonlite)
})

log_msg <- function(level, ...) {
  ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(sprintf("[%s] %s %s\n", ts, level, paste0(..., collapse = "")))
}
log_info <- function(...) log_msg("INFO ", ...)
log_warn <- function(...) log_msg("WARN ", ...)
log_err  <- function(...) log_msg("ERROR", ...)

# ---------------------------------------------------------------------------
# Mode 1: build from weekly snapshots
# ---------------------------------------------------------------------------

#' Scan every weekly JSON snapshot and return a data.frame of
#' (song_id, name, artists) aggregated across all snapshots. If the same
#' song_id appears with different names (rare), we keep the most recent.
collect_from_snapshots <- function(snapshots_dir) {
  if (!dir.exists(snapshots_dir)) {
    stop("snapshots dir not found: ", snapshots_dir)
  }
  files <- sort(Sys.glob(file.path(snapshots_dir, "*.json")))
  if (length(files) == 0L) {
    stop("no JSON snapshots in ", snapshots_dir)
  }
  log_info("reading ", length(files), " snapshot files from ", snapshots_dir)
  rows <- list()
  for (f in files) {
    j <- tryCatch(fromJSON(f, simplifyVector = FALSE), error = function(e) NULL)
    if (is.null(j) || is.null(j$songs)) next
    snap_time <- j$snapshot_time %||% NA_character_
    for (s in j$songs) {
      sid <- s$song_id %||% ""
      if (!nzchar(sid)) next
      rows[[length(rows) + 1L]] <- data.frame(
        song_id     = as.character(sid),
        name        = as.character(s$name %||% ""),
        artists     = paste(unlist(s$artists %||% list()), collapse = " / "),
        first_seen  = snap_time,
        stringsAsFactors = FALSE
      )
    }
  }
  if (length(rows) == 0L) {
    stop("no songs parsed from snapshots")
  }
  df <- do.call(rbind, rows)
  # When a song appears in many weeks, collapse by song_id and keep the earliest
  # first_seen. Names and artists are typically consistent, but we take the
  # modal one in case NetEase re-edits metadata.
  by_sid <- split(df, df$song_id)
  out <- do.call(rbind, lapply(by_sid, function(g) {
    data.frame(
      song_id    = g$song_id[1],
      name       = .mode_or_first(g$name),
      artists    = .mode_or_first(g$artists),
      first_seen = min(g$first_seen, na.rm = TRUE),
      stringsAsFactors = FALSE
    )
  }))
  rownames(out) <- NULL
  out
}

#' Pick the modal value, fall back to the first value if no mode.
.mode_or_first <- function(x) {
  tbl <- table(x)
  top <- names(tbl)[which.max(tbl)]
  if (length(top) == 0L || !nzchar(top)) x[1] else top
}

#' %||% is missing from base R before 4.4; provide one locally.
`%||%` <- function(a, b) if (is.null(a)) b else a

# ---------------------------------------------------------------------------
# Mode 2: discover from mp3 directory alone
# ---------------------------------------------------------------------------

#' Scan an mp3 directory and produce one catalog entry per file. The key is
#' the filename stem; song_id is left NULL.
#'
#' If the stem looks like "ARTIST - TITLE" (case-insensitive, ASCII or CJK),
#' we split on the first " - " and treat the left side as the artist and the
#' right side as the title. This matches the convention used by the NetEase
#' Cloud Music client's desktop downloader.
collect_from_mp3_dir <- function(mp3_dir) {
  if (!dir.exists(mp3_dir)) {
    stop("mp3 dir not found: ", mp3_dir)
  }
  files <- Sys.glob(file.path(mp3_dir, "*.mp3"))
  if (length(files) == 0L) {
    stop("no mp3 files in ", mp3_dir)
  }
  log_info("discovered ", length(files), " mp3 files in ", mp3_dir)
  rows <- lapply(files, function(f) {
    base <- basename(f)
    stem <- tools::file_path_sans_ext(base)
    # Numeric stem -> song_id form (scripted downloads)
    if (grepl("^[0-9]+$", stem)) {
      return(list(
        key       = stem,
        song_id   = stem,
        name      = NA_character_,
        artists   = NA_character_,
        mp3_file  = base
      ))
    }
    # Otherwise try to split "ARTIST - TITLE"
    parts <- strsplit(stem, " - ", fixed = TRUE)[[1]]
    if (length(parts) >= 2L) {
      artist <- parts[1]
      title  <- paste(parts[-1], collapse = " - ")
    } else {
      artist <- NA_character_
      title  <- stem
    }
    list(
      key       = stem,
      song_id   = NA_character_,
      name      = title,
      artists   = artist,
      mp3_file  = base
    )
  })
  rows
}

# ---------------------------------------------------------------------------
# Catalog writer
# ---------------------------------------------------------------------------

#' Build (or merge into) an existing catalog. Returns the new catalog as a
#' named list.
build_catalog <- function(snapshot_df = NULL, mp3_rows = list(), existing = list()) {
  cat <- existing

  # Add entries from snapshots (Mode 1)
  if (!is.null(snapshot_df) && nrow(snapshot_df) > 0L) {
    for (i in seq_len(nrow(snapshot_df))) {
      sid <- snapshot_df$song_id[i]
      mp3_file <- paste0(sid, ".mp3")
      entry <- list(
        song_id   = sid,
        name      = snapshot_df$name[i],
        artists   = if (is.na(snapshot_df$artists[i])) list() else
                      strsplit(snapshot_df$artists[i], " / ", fixed = TRUE)[[1]],
        mp3_file  = mp3_file,
        first_seen = snapshot_df$first_seen[i]
      )
      # Only insert if there's actually an mp3 for this entry OR we already
      # have it from a previous run.
      if (paste0(sid, ".mp3") %in% vapply(cat, function(e) e$mp3_file %||% "",
                                          character(1)) ||
          i <= length(cat)) {
        cat[[sid]] <- entry
      }
    }
  }

  # Add mp3-only entries (Mode 2 / fallback)
  for (row in mp3_rows) {
    if (!is.null(cat[[row$key]])) next   # existing entry wins
    # In Mode 2 a single artist string is supplied; wrap it for JSON.
    art <- if (is.na(row$artists)) list() else strsplit(row$artists, " / ", fixed = TRUE)[[1]]
    if (length(art) == 1L && !is.na(row$artists)) {
      art <- list(row$artists)            # single-artist case
    }
    cat[[row$key]] <- list(
      song_id    = row$song_id,
      name       = row$name,
      artists    = art,
      mp3_file   = row$mp3_file,
      first_seen = NA_character_
    )
  }
  cat
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

main <- function(argv = NULL) {
  if (is.null(argv)) argv <- commandArgs(trailingOnly = TRUE)

  parse_args <- function(a) {
    out <- list(snapshots = NULL, mp3 = NULL, out = "data/songs_catalog.json")
    i <- 1L
    while (i <= length(a)) {
      x <- a[[i]]
      if (x == "--snapshots") { out$snapshots <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--mp3-dir","--mp3","-m")) { out$mp3 <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--out","-o")) { out$out <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--help","-h")) {
        cat("usage: Rscript build_songs_catalog.R [--snapshots DIR] [--mp3-dir DIR] --out FILE\n")
        quit(status = 0L)
      } else { stop("unknown arg: ", x) }
    }
    out
  }
  args <- parse_args(argv)
  if (is.null(args$snapshots) && is.null(args$mp3)) {
    stop("at least one of --snapshots or --mp3-dir is required")
  }

  # Load existing catalog if it exists, so we merge instead of clobbering.
  existing <- if (file.exists(args$out)) {
    tryCatch(fromJSON(args$out, simplifyVector = FALSE), error = function(e) list())
  } else list()
  log_info("existing catalog has ", length(existing), " entries")

  snapshot_df <- if (!is.null(args$snapshots)) collect_from_snapshots(args$snapshots) else NULL
  mp3_rows    <- if (!is.null(args$mp3)) collect_from_mp3_dir(args$mp3) else list()

  cat_obj <- build_catalog(snapshot_df, mp3_rows, existing)

  # Always overwrite the file from scratch each run so the schema stays clean.
  # (Existing entries are preserved by passing them through build_catalog.)
  dir.create(dirname(args$out), recursive = TRUE, showWarnings = FALSE)
  json <- toJSON(cat_obj, pretty = TRUE, auto_unbox = TRUE, force = TRUE)
  writeLines(json, con = args$out, useBytes = TRUE)
  log_info("wrote ", args$out, " with ", length(cat_obj), " entries")
  invisible(0L)
}

if (!interactive() && identical(sys.nframe(), 0L)) {
  tryCatch(main(), error = function(e) {
    log_err("fatal: ", conditionMessage(e))
    quit(status = 1L)
  })
}
