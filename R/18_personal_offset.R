#' 18_personal_offset.R
#' =====================
#'
#' Compute a user's "personal offset" from the QQ Music 137K mainstream
#' centroid, in two ways:
#'
#'   1. Categorical distribution: how do the user's songs distribute
#'      across QQ's seven toplists and three inferred genres, compared to
#'      the overall 137K distribution? We compute KL divergence of the
#'      user's per-genre frequency vector against the QQ 137K prior.
#'
#'   2. Chart-history feature space: project each user song onto the QQ
#'      137K 5-dimensional feature space (weeks_total, peak_rank_min,
#'      top_ids_present, etc.) and compute Mahalanobis distance to the
#'      overall QQ centroid.
#'
#' Inputs
#' ------
#'   user_csv     -- path to a user CSV with columns song_id (or qq_id /
#'                   netease_id, see --platform), song_name, artist
#'   qq_center    -- path to the QQ 137K summary CSV (produced by the
#'                   friend's 01_clean.R, written to
#'                   sound_of_decade/data/interim/song_year_all.csv).
#'                   If NULL, the function emits a clear error explaining
#'                   where the QQ baseline lives.
#'   --platform   -- one of "qq", "netease", "auto". Default "auto".
#'                   "auto" reads a `#! platform: qq` (or netease) header
#'                   in the user CSV; falls back to qq on no header.
#'
#' Output
#' ------
#'   A list with:
#'     $categorical  -- data.frame(category, user_count, qq_count,
#'                                  user_freq, qq_freq, kl_contribution)
#'     $kl_total      -- scalar, sum of kl_contribution
#'     $feature_space -- data.frame(song_name, mahalanobis_dist,
#'                                   z_score) for each matched user song
#'     $summary       -- one-row data.frame with overall verdict
#'     $meta          -- list of run metadata (n_input, n_matched, etc.)
#'
#' Usage
#' -----
#'   source("R/18_personal_offset.R")
#'   out <- compute_personal_offset(
#'     user_csv  = "data/examples/example_user.csv",
#'     qq_center = "sound_of_decade/data/interim/song_year_all.csv"
#'   )
#'   print(out$summary)

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(tidyr); library(stringr); library(jsonlite)
})

log_msg <- function(level, ...) {
  ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(sprintf("[%s] %s %s\n", ts, level, paste0(..., collapse="")))
}
log_info <- function(...) log_msg("INFO ", ...)
log_warn <- function(...) log_msg("WARN ", ...)
log_err  <- function(...) log_msg("ERROR", ...)

# ---------------------------------------------------------------------------
# 0. CSV ingestion (with #! meta-block support)
# ---------------------------------------------------------------------------

#' Read a user CSV. The format is "ordinary CSV" but lines starting with
#' `#! key: value` at the top are treated as a meta block: extracted into
#' `meta` and removed before the table is parsed.
#'
#' The data block must have a header row. Required columns: song_id OR
#' qq_id OR netease_id (at least one), and song_name, artist.
#'
#' Recognised meta keys: `platform`, `description`, anything else is kept
#' as-is.
read_user_csv <- function(path, platform_override = NULL) {
  if (!file.exists(path)) stop("user CSV not found: ", path)
  raw_lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  meta_lines   <- grep("^#!", raw_lines, value = TRUE)
  data_lines   <- raw_lines[!grepl("^#", raw_lines)]
  meta <- list()
  for (ln in meta_lines) {
    kv <- sub("^#!\\s*", "", ln)
    parts <- strsplit(kv, ":\\s*", fixed = FALSE)[[1]]
    if (length(parts) >= 2L) {
      key <- parts[1]
      val <- paste(parts[-1], collapse = ": ")
      meta[[key]] <- val
    }
  }
  tmp <- tempfile(fileext = ".csv")
  on.exit(unlink(tmp), add = TRUE)
  writeLines(data_lines, tmp, useBytes = TRUE)

  delim <- ","  # simple: the example CSV is comma-only
  df <- readr::read_delim(tmp, delim = delim,
                          col_types = readr::cols(.default = readr::col_character()),
                          show_col_types = FALSE, progress = FALSE,
                          locale = readr::locale(encoding = "UTF-8"))

  # Platform resolution
  platform <- platform_override %||% meta$platform %||% "auto"
  if (platform == "auto") {
    # Heuristic: if column `netease_id` exists and is non-empty, treat
    # as netease; else QQ.
    platform <- if ("netease_id" %in% names(df) &&
                   any(!is.na(df$netease_id) & nzchar(df$netease_id))) {
      "netease"
    } else {
      "qq"
    }
  }
  id_col <- switch(platform,
                   qq      = "qq_id",
                   netease = "netease_id",
                   stop("unknown platform: ", platform))

  if (!id_col %in% names(df)) {
    stop("platform '", platform, "' but CSV has no column `", id_col, "`")
  }
  df$platform <- platform
  df$user_id  <- trimws(df[[id_col]])
  df <- df[!is.na(df$user_id) & nzchar(df$user_id), , drop = FALSE]

  list(df = df, meta = meta, platform = platform)
}

#' `%||%` (null-coalesce) for backwards compatibility with R < 4.4.
`%||%` <- function(a, b) if (is.null(a)) b else a

# ---------------------------------------------------------------------------
# 1. Categorical distribution (genre + toplist)
# ---------------------------------------------------------------------------

#' Expand a comma/slash/and-separated artist string into a character
#' vector. Same logic as import_personal_excel.R / build_songs_catalog.R.
split_artists <- function(s) {
  if (is.na(s) || !nzchar(s)) return(character(0))
  s <- gsub("\\s*(feat\\.?|ft\\.?)\\s*", ",", s, perl = TRUE, ignore.case = TRUE)
  s <- gsub("[,&/|+]+", ",", s)
  s <- gsub("\xe3\x80\x81", ",", s, useBytes = TRUE)
  s <- gsub("\xef\xbc\x8c", ",", s, useBytes = TRUE)
  parts <- strsplit(s, ",", fixed = TRUE)[[1]]
  parts <- trimws(parts)
  parts[nzchar(parts)]
}

#' A "category" is one of the seven QQ toplists. We assign each user
#' song to one or more toplists using the QQ baseline's own inferred
#' membership. If the user CSV has a `genre` column we use that as an
#' additional category dimension.
assign_categories <- function(user_df, qq_summary) {
  # Try to join each user song to QQ 137K by song_id, and inherit the
#  list of (top_id, top_title) it ever appeared in. Fallback: by song
#  name fuzzy match.
  user_df$song_id_chr <- as.character(user_df$user_id)
  user_df$matched <- "unmatched"

  if (!is.null(qq_summary) && "song_id" %in% names(qq_summary)) {
    # Use the QQ baseline's per-song-year summary
    by_id <- qq_summary |>
      dplyr::select(song_id, song_title, singer_name, year,
                    weeks_total, peak_rank_min, top_ids_present, genres) |>
      dplyr::mutate(song_id_chr = as.character(song_id))

    # First pass: exact song_id match
    keys <- intersect(c("song_id_chr", "song_title", "singer_name"),
                      names(by_id))
    if ("song_id_chr" %in% names(by_id)) {
      user_with_idx <- user_df |>
        dplyr::mutate(.row_id = seq_len(dplyr::n()))
      hits <- dplyr::inner_join(
        user_with_idx |> dplyr::select(.row_id, user_id, song_name, artist, genre, platform),
        by_id |> dplyr::group_by(song_id_chr) |>
          dplyr::summarise(year_min = min(year),
                            year_max = max(year),
                            weeks_total_max = max(weeks_total),
                            peak_rank_min = min(peak_rank_min),
                            top_ids_present_max = max(top_ids_present),
                            genres_union = paste(unique(genres), collapse=","),
                            .groups = "drop"),
        by = c("user_id" = "song_id_chr")
      )
      if (nrow(hits) > 0L) {
        user_df$matched[as.integer(hits$.row_id)] <- "by_id"
      }
    }

    # Second pass: fuzzy by song_title + singer_name for unmatched
    still_unmatched <- user_df$matched == "unmatched"
    if (any(still_unmatched, na.rm = TRUE)) {
      for (i in which(still_unmatched)) {
        title <- user_df$song_name[i]
        artist <- user_df$artist[i]
        if (is.na(title) || !nzchar(title)) next
        cands <- by_id |>
          dplyr::filter(song_title == title) |>
          dplyr::filter(is.na(singer_name) | grepl(artist, song_title, fixed = TRUE))
        if (nrow(cands) > 0L) {
          user_df$matched[i] <- "by_name"
        }
      }
    }
  }
  user_df
}

#' Compute per-category counts/freq for the user vs the QQ baseline, then
#' KL(user || qq).
#'
#' The categorical axis is "toplist" (one of the seven QQ charts). We
#' use the per-song-per-topid long-form CSV (the friend's raw data) so
#' each row gives a (song_id, top_id, top_title) triple. The summary CSV
#' `song_year_all.csv` collapses across toplists and therefore loses
#' the categorical axis.
categorical_kl <- function(user_df, qq_center_path) {
  if (is.null(qq_center_path) || !file.exists(qq_center_path)) {
    log_warn("categorical_kl: no qq_center_path; returning NA")
    return(list(kl = NA_real_, by_category = NULL, matched = 0L))
  }
  # Resolve to the per-to pid long-form CSV by replacing the file name.
  long_path <- sub("song_year_all\\.csv$",
                   "raw/qq/qq_topId{26}_weekly_long.csv",
                   qq_center_path)
  if (!file.exists(long_path)) {
    long_path <- file.path(dirname(dirname(qq_center_path)), "raw", "qq",
                           "qq_topId26_weekly_long.csv")
  }
  if (!file.exists(long_path)) {
    log_warn("categorical_kl: could not find a per-song long-form QQ CSV")
    return(list(kl = NA_real_, by_category = NULL, matched = 0L))
  }
  log_info("categorical_kl: loading long-form ", long_path)
  long_df <- readr::read_csv(long_path, show_col_types = FALSE,
                             progress = FALSE,
                             locale = readr::locale(encoding = "UTF-8"))
  top_col <- intersect(c("top_title", "top_name", "chart_name", "name"),
                       names(long_df))[1]
  if (is.na(top_col)) top_col <- "top_id"

  # All QQ toplists have a single value here (e.g. "热歌榜"), so we
  # compare the user's match-rate to the QQ chart's distinct-song count
  # for each year. If we had all 7 toplists, this would be a real KL over
  # the toplist axis; for now it's a per-year presence rate.
  qq_by_ct <- long_df |>
    dplyr::group_by(year = as.integer(substr(period, 1, 4))) |>
    dplyr::summarise(qq_count = dplyr::n_distinct(song_id), .groups = "drop")

  matched <- user_df |> dplyr::filter(matched != "unmatched")
  if (nrow(matched) == 0L) {
    log_warn("no matched songs; categorical divergence is undefined")
    return(list(kl = NA_real_, by_category = qq_by_ct, matched = 0L))
  }

  # We don't know which toplist the user heard their songs on, so the
  # best we can do is count how many of the user's songs are in each
  # year of QQ's top chart.
  user_by_yr <- data.frame(year = integer(0),
                           user_count = integer(0))
  # The summary has per-year + weeks_total / peak_rank_min; we re-derive
  # by looking up matched songs in qq_summary
  qq_summary_for_year <- NULL
  if (!is.null(qq_center_path) && file.exists(qq_center_path)) {
    qq_summary_for_year <- readr::read_csv(qq_center_path,
                                           show_col_types = FALSE,
                                           progress = FALSE,
                                           locale = readr::locale(encoding = "UTF-8"))
  }
  if (!is.null(qq_summary_for_year) && nrow(qq_summary_for_year) > 0L) {
    user_years <- qq_summary_for_year |>
      dplyr::filter(as.character(song_id) %in% as.character(matched$user_id))
    if (nrow(user_years) > 0L) {
      user_by_yr <- user_years |>
        dplyr::group_by(year) |>
        dplyr::summarise(user_count = dplyr::n_distinct(song_id), .groups = "drop")
    }
  }

  merged <- merge(qq_by_ct, user_by_yr, by = "year", all.x = TRUE)
  merged$user_count[is.na(merged$user_count)] <- 0L

  total_user <- sum(merged$user_count)
  total_qq   <- sum(merged$qq_count)
  k <- nrow(merged)
  p_user <- (merged$user_count + 1) / (total_user + k)
  p_qq   <- (merged$qq_count   + 1) / (total_qq   + k)
  merged$kl_contribution <- ifelse(merged$user_count == 0, 0,
                                  p_user * log(p_user / p_qq))
  kl_total <- sum(merged$kl_contribution)

  list(kl = kl_total, by_category = merged, matched = nrow(matched))
}

# ---------------------------------------------------------------------------
# 2. Chart-history feature space distance
# ---------------------------------------------------------------------------

#' Build  the QQ 137K feature-space centroid + inverse-covariance for
# '  Mahalanobis distance.
#'
#' The input is the per-song-per-year summary already collapsed by the
#' friend to one row per (year, song_id). We further collapse across
#' years to get one row per song_id (taking the min year, max weeks,
#' min peak_rank, max top_ids_present -- i.e. each song's "career best").
qq_feature_baseline <- function(qq_summary) {
  if (is.null(qq_summary)) return(NULL)
  feats <- qq_summary |>
    dplyr::mutate(song_id_chr = as.character(song_id)) |>
    dplyr:: group_by(song_id_chr) |>
    dplyr::summarise(
      year              = min(year),
      weeks_total_max   = max(weeks_total),
      peak_rank_min_min = min(peak_rank_min),
      top_ids_present_max = max(top_ids_present),
      .groups = "drop"
    ) |>
    dplyr::filter(!is.na(weeks_total_max),
                  !is.na(peak_rank_min_min),
                  !is.na(top_ids_present_max),
                  !is.na(year)) |>
    dplyr::mutate(
      f_year            = year - 2020,
      f_weeks_total     = weeks_total_max / 50,
      f_log_weeks_total = log1p(weeks_total_max) / 4,
      f_peak_rank_min   = (101 - peak_rank_min_min) / 100,
      f_top_ids_present = top_ids_present_max / 7
    )

  if (nrow(feats) < 5L) return(NULL)
  X <- as.matrix(feats[, c("f_year", "f_weeks_total", "f_log_weeks_total",
                            "f_ peak_rank_min", "f_top_ids_present")])
  mu <- colMeans(X)
  S <- cov(X)
  if (any(diag(S) < 1e-6)) S <- S + 1e-3 * diag(ncol(S))
  invS <- tryCatch(solve(S), error = function(e) NULL)
  if (is.null(invS)) return(NULL)

  # Build per-song lookup keyed by character song_id
  feats_l <- split(feats, feats$song_id_chr)
  lookup <- lapply(feats_l, function(df) {
    list(
      year              = df$year[1],
      weeks_total       = df$weeks_total_max[1],
      peak_rank_min     = df$peak_rank_min_min[1],
      top_ids_present   = df$top_ids_present_max[1],
      f_year            = df$f_year[1],
      f_weeks_total     = df$f_weeks_total[1],
      f_log_weeks_total = df$f_log_weeks_total[1],
      f_peak_rank_min   = df$f_peak_rank_min[1],
      f_top_ids_present = df$f_top_ids_present[1]
    )
  })

  # Reference distribution for z-score:   compute  Mahalanobis distance for every
  # baseline song once, up front. Sampling at max 2000 points keeps the
  # runtime bounded.
  ids <- names(lookup)
  if (length(ids) > 2000L) ids <- ids[seq(1, length(ids), length.out = 2000L)]
  ref_d <- vapply(ids, function(sid2) {
    b <- lookup[[sid2]]
    X <- matrix(c(b$f_year, b$f_weeks_total, b$f_log_weeks_total,
                  b$f_peak_rank_min, b$f_top_ids_present), nrow = 1L)
    d2 <- mahalanobis(X, center = mu, cov = invS, inverted = TRUE)
    sqrt(as.numeric(d2))
  }, numeric(1))
  ref_sd <- sd(ref_d, na.rm = TRUE)
  ref_mu <- mean(ref_d, na.rm = TRUE)

  list(mu = mu, invS = invS, lookup = lookup, ids = names(lookup),
  ref_sd = ref_sd, ref_mu = ref_mu)
}

#' For each user song with a QQ match, project it onto the feature space
#' and compute Mahalanobis distance + z-score.
mahalanobis_per_song <- function(user_df, baseline) {
  if (is.null(baseline)) return(NULL)
  matched <- user_df |>
    dplyr::filter(matched != "unmatched")
  if (nrow(matched) == 0L) return(NULL)

  rows <- list()
  for (i in seq_len(nrow(matched))) {
    sid <- as.character(matched$user_id[i])
    b <- baseline$lookup[[sid]]
    if (is.null(b)) next
    X <- matrix(c(b$f_year, b$f_weeks_total, b$f_log_weeks_total,
                  b$f_peak_rank_min, b$f_top_ids_present),
                nrow = 1L)
    d2 <- mahalanobis(X, center = baseline$mu, cov = baseline$invS,
                      inverted = TRUE)
    rows[[length(rows) + 1L]] <- data.frame(
      song_name      = matched$song_name[i],
      artist         = matched$artist[i],
      year           = b$year,
      weeks_total    = b$weeks_total,
      peak_rank_min  = b$peak_rank_min,
      top_ids_present = b$top_ids_present,
      mahalanobis    = sqrt(as.numeric(d2)),
      stringsAsFactors = FALSE
    )
  }
  if (length(rows) == 0L) return(NULL)
  out <- do.call(rbind, rows)
  # z-score = (distance - reference mean) / reference sd. The reference
  # distribution was pre-computed in qq_feature_baseline(); see the comment
  # there for details.
  if ( is.finite(baseline$ref_sd) && baseline$ref_sd > 0) {
    out$z_score <- (out$mahalanobis - baseline$ref_mu) / baseline$ref_sd
  } else {
    out$z_score <- NA_real_
  }
  out
}

# ---------------------------------------------------------------------------
# 3. Top-level driver
# ---------------------------------------------------------------------------

#' Run the personal-offset analysis end-to-end.
#'
#' @param user_csv   path to user CSV
#' @param qq_center  path to the QQ 137K baseline CSV
#'         (data/interim/song_year_all.csv from the friend's pipeline)
#' @param platform_override "qq" / "netease" / "auto" (default)
#' @return list with $categorical, $feature_space, $summary, $meta
compute_personal_offset <- function(user_csv,
                                   qq_center = NULL,
                                   platform_override = NULL) {
  log_info("user_csv=", user_csv)
  log_info("qq_center=", if (is.null(qq_center)) "<not provided>" else qq_center)

  # Load user CSV (with #! meta block)
  parsed <- read_user_csv(user_csv, platform_override = platform_override)
  user_df <- parsed$df
  meta    <- parsed$meta
  platform <- parsed$platform
  log_info("read ", nrow(user_df), " user rows; platform=", platform)

  # Load QQ baseline if provided
  qq_summary <- NULL
  if (!is.null(qq_center) && file.exists(qq_center)) {
    log_info("loading QQ baseline: ", qq_center)
    # The friend's pipeline writes CSV in UTF-8; on Windows the bytes look
    # like `<U+XXXX>` escapes to the R console but are valid UTF-8 under
    # the hood. readr's default UTF-8 locale reads them correctly.
    qq_summary <- readr::read_csv(qq_center, show_col_types = FALSE,
                                  progress = FALSE,
                                  locale = readr::locale(encoding = "UTF-8"))
    log_info("QQ baseline rows: ", nrow(qq_summary))
  } else {
    log_warn("QQ baseline not provided; feature-space path will be skipped")
  }

  # Match user songs to QQ 137K
  user_df <- assign_categories(user_df, qq_summary)
  n_matched <- sum(user_df$matched != "unmatched")
  log_info("matched: ", n_matched, "/", nrow(user_df))

  # Categorical divergence
  cat_res <- categorical_kl(user_df, qq_center)
  log_info("categorical KL = ", round(cat_res$kl, 3))

  # Feature-space distance (only if baseline present)
  fs_res <- NULL
  if (!is.null(qq_summary)) {
    baseline <- qq_feature_baseline(qq_summary)
    fs_res <- mahalanobis_per_song(user_df, baseline)
  }

  summary <- data.frame(
    n_input          = nrow(user_df),
    n_matched        = n_matched,
    matched_frac     = if (nrow(user_df) > 0) n_matched / nrow(user_df) else NA_real_,
    kl_divergence    = cat_res$kl,
    feature_space_avg= if (!is.null(fs_res)) mean(fs_res$z_score) else NA_real_,
    stringsAsFactors = FALSE
  )

  list(
    categorical  = cat_res,
    feature_space = fs_res,
    summary      = summary,
    meta         = list(
      user_csv    = user_csv,
      qq_center   = qq_center,
      platform    = platform,
      csv_meta    = meta,
      run_time    = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z")
    )
  )
}

# ---------------------------------------------------------------------------
# 4. CLI
# ---------------------------------------------------------------------------

main <- function(argv = NULL) {
  if (is.null(argv)) argv <- commandArgs(trailingOnly = TRUE)
  parse_args <- function(a) {
    out <- list(user = NULL, qq = NULL, platform = NULL, out_json = NULL,
                top_n = 20L)
    i <- 1L
    while (i <= length(a)) {
      x <- a[[i]]
      if (x %in% c("--user","-u")) { out$user <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--qq") { out$qq <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--platform") { out$platform <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--out") { out$out_json <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--top-n") { out$top_n <- as.integer(a[[i + 1L]]); i <- i + 2L
      } else if (x %in% c("--help","-h")) {
        cat("usage: Rscript 18_personal_offset.R --user CSV --qq QQ_BASELINE_CSV [--out JSON] [--platform qq|netease|auto]\n")
        quit(status = 0L)
      } else { stop("unknown arg: ", x) }
    }
    out
  }
  args <- parse_args(argv)
  if (is.null(args$user)) stop("--user is required")

  res <- compute_personal_offset(
    user_csv          = args$user,
    qq_center         = args$qq,
    platform_override = args$platform
  )
  cat("\n=========== SUMMARY ===========\n")
  print(res$summary, row.names = FALSE)

  if (!is.null(args$out_json)) {
    dir.create(dirname(args$out_json), recursive = TRUE, showWarnings = FALSE)
    jsonlite::toJSON(res, pretty = TRUE, auto_unbox = TRUE, force = TRUE) |>
      jsonlite::prettify() |>
      writeLines(args$out_json, useBytes = TRUE)
    log_info("wrote ", args$out_json)
  }
  invisible(0L)
}

if (!interactive() && identical(sys.nframe(), 0L)) {
  tryCatch(main(), error = function(e) {
    log_err("fatal: ", conditionMessage(e))
    quit(status = 1L)
  })
}