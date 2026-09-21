#' extract_audio_features.R
#' ========================
#'
#' Extract per-song feature vectors from .mp3 files using classical MIR
#' descriptors. R-only, no Python.
#'
#' Why classical features, not a pretrained embedding?
#' ---------------------------------------------------
#' The original design (DESIGN.md v1) preferred Jukemir / MusicNN / CLAP, all
#' of which live in Python. Switching to a 100% R stack (see the project
#' README) meant dropping those. The replacement is a battery of well-known
#' MIR descriptors that ship in CRAN packages:
#'
#'   * MFCC       (Mel-frequency cepstral coefficients) — `tuneR::melfcc()`
#'   * Spectral   (centroid, bandwidth, flatness)       — custom FFT-based
#'   * Chroma     (12 pitch class energies)             — custom FFT + binning
#'   * Tempo / ZCR — `seewave::timer()`, `seewave::zcr()`
#'
#' These are not as semantically rich as a Jukebox embedding, but they are
#' interpretable, fast on CPU, and acceptable for a course project where the
#' *story* (5-year drift) matters more than feature dimensionality.
#'
#' A note on seewave 2.2.x: the package still ships `timer` and `zcr`, but
#' `mfcc` and `chroma` were removed from the public API in late releases. We
#' therefore use `tuneR::melfcc()` for MFCCs and a small custom chroma
#' implementation (FFT magnitude spectrum → 12-bin pitch-class folding).
#'
#' Output
#' ------
#' `data/embeddings/song_features.csv`
#'
#'   song_id, mfcc_1, ..., mfcc_13, spec_centroid, spec_bandwidth,
#'   spec_flatness, C, C#, D, ..., B, tempo, zcr
#'
#' Plus `data/embeddings/song_features_failures.csv` listing songs we could
#' not process and the reason. This is small, machine-readable, and committed
#' to the repo so we never lose track of why songs are missing.
#'
#' Usage
#' -----
#'   Rscript R/extract_audio_features.R --src data/mp3 --out data/embeddings \
#'       --catalog data/songs_catalog.json

suppressPackageStartupMessages({
  if (!requireNamespace("tuneR",   quietly = TRUE)) stop("tuneR is required: install.packages('tuneR')")
  if (!requireNamespace("seewave", quietly = TRUE)) stop("seewave is required: install.packages('seewave')")
  if (!requireNamespace("jsonlite",quietly = TRUE)) stop("jsonlite is required: install.packages('jsonlite')")
  library(tuneR)
  library(seewave)
  library(jsonlite)
})

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_msg <- function(level, ...) {
  ts <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(sprintf("[%s] %s %s\n", ts, level, paste0(..., collapse="")))
}
log_info <- function(...) log_msg("INFO ", ...)
log_warn <- function(...) log_msg("WARN ", ...)
log_err  <- function(...) log_msg("ERROR", ...)

# ---------------------------------------------------------------------------
# Feature extraction for one song
# ---------------------------------------------------------------------------

#' Read one mp3 into a tuneR Wave object, downmixed to mono + resampled.
#'
#' `max_seconds` (default 60) truncates the wave to the first N seconds. The
#' pipeline only needs enough audio to estimate global descriptors; a full
#' 4-minute track makes `seewave::timer` take minutes per song. 60 seconds is
#' a good compromise: long enough to capture the song's main section, short
#' enough that the batch finishes in seconds.
read_mp3_mono <- function(path, target_sr = 22050, max_seconds = 60) {
  w <- tuneR::readMP3(path)
  # Always mono mixdown FIRST, then truncate. This way the truncation works
  # on a single-channel wave and we avoid the "channels must have same length"
  # validation error that stereo + truncate triggers.
  if (w@stereo) {
    w <- tuneR::mono(w, which = "both")
  }
  # Now truncate (max_seconds).
  if (!is.null(max_seconds) && max_seconds > 0) {
    max_samples <- as.integer(target_sr * max_seconds)
    if (length(w@left) > max_samples) {
      w@left <- w@left[seq_len(max_samples)]
    }
  }
  # Resample to a fixed SR to keep MFCC dimensions stable across songs.
  # NOTE: we use tuneR::downsample rather than seewave::resamp because the
  # latter (2.2.4) requires a positional `g` argument and silently raises
  # "argument g is missing" when called with f=. It's also tied to the
  # WaveGeneral class, which is stricter than what we want for a quick
  # mono resample. downsample() is the simpler, well-tested choice.
  if (w@samp.rate != target_sr) {
    w <- tuneR::downsample(w, target_sr)
  }
  w
}

#' Frame a mono signal into overlapping windows. Returns a numeric matrix
#' (n_frames x win_length). Centre-aligned windowing is not required for the
#' coarse features we compute.
.frame_signal <- function(x, win = 1024L, hop = 512L) {
  n  <- length(x)
  if (n < win) {
    return(matrix(c(x, rep(0, win - n)), nrow = 1L))
  }
  starts <- seq(1L, n - win + 1L, by = hop)
  vapply(starts, function(s) x[s:(s + win - 1L)], numeric(win))
}

#' Mean and (population) sd of the magnitude spectrum across frames, in Hz.
#' Returns centroid, bandwidth (=sd), and a flatness proxy on the linear
#' magnitude spectrum.
.spectral_props <- function(x, sr, win = 1024L, hop = 512L) {
  frames <- .frame_signal(x, win = win, hop = hop)
  win_h  <- seewave::hanning.w(win)
  frames <- frames * win_h
  mags   <- Mod(stats::mvfft(frames)) / win   # n_freq x n_frames
  mags   <- mags[seq_len(floor(win / 2) + 1L), , drop = FALSE]   # keep positive freqs
  freqs  <- (0:(nrow(mags) - 1L)) * sr / win
  # Broadcast: freqs is length(n_freq), mags is n_freq x n_frames -> sweep columns
  freqs_mat <- matrix(freqs, nrow = nrow(mags), ncol = ncol(mags))

  # Per-frame centroid & sd (in Hz), then average.
  denom <- colSums(mags) + .Machine$double.eps
  cent  <- colSums(mags * freqs_mat) / denom
  diff  <- freqs_mat - matrix(cent, nrow = nrow(mags), ncol = ncol(mags), byrow = TRUE)
  var_  <- colSums(mags * diff^2) / denom
  sd_   <- sqrt(pmax(var_, 0))

  # Spectral flatness: geometric mean / arithmetic mean of magnitudes, per frame.
  log_mags   <- log(mags + .Machine$double.eps)
  geo_mean   <- exp(colMeans(log_mags))
  arith_mean <- colMeans(mags)
  flatness   <- geo_mean / (arith_mean + .Machine$double.eps)

  c(
    spec_centroid  = mean(cent,    na.rm = TRUE),
    spec_bandwidth = mean(sd_,     na.rm = TRUE),
    spec_flatness  = mean(flatness,na.rm = TRUE)
  )
}

#' 12-bin pitch-class chroma from a signal. Returns a length-12 normalised
#' vector whose names are c("C","C#","D",...,"B").
.chroma_12 <- function(x, sr, win = 4096L, hop = 2048L) {
  frames <- .frame_signal(x, win = win, hop = hop)
  win_h  <- seewave::hanning.w(win)
  frames <- frames * win_h
  mags   <- Mod(stats::mvfft(frames)) / win
  mags   <- mags[seq_len(floor(win / 2) + 1L), , drop = FALSE]
  freqs  <- (0:(nrow(mags) - 1L)) * sr / win
  # Keep only musically useful range: ~65 Hz (C2) to ~2000 Hz.
  keep   <- freqs >= 65 & freqs <= 2000
  mags   <- mags[keep, , drop = FALSE]
  freqs  <- freqs[keep]
  if (length(freqs) == 0L) {
    return(setNames(rep(0, 12), c("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")))
  }
  # Fold each bin into the closest pitch class. Reference = A4 = 440 Hz.
  midi   <- 69 + 12 * log2(freqs / 440)
  pc     <- ((round(midi) - 1L) %% 12L) + 1L   # 1..12, where 1 = C
  energy <- rowMeans(mags)
  chroma <- vapply(seq_len(12L), function(k) sum(energy[pc == k]), numeric(1))
  chroma <- chroma / max(sum(chroma), .Machine$double.eps)
  setNames(chroma, c("C","C#","D","D#","E","F","F#","G","G#","A","A#","B"))
}

#' Compute the full feature vector for one wave. Returns a named numeric vector.
compute_features <- function(w, n_mfcc = 13L) {
  sr <- w@samp.rate
  v  <- w@left / (2 ^ (w@bit - 1))   # normalise to [-1, 1]

  # --- MFCC: tuneR::melfcc expects a Wave object, not a numeric vector ---
  mf <- tryCatch(
    tuneR::melfcc(w, sr = sr, numcep = n_mfcc),
    error = function(e) NULL
  )
  if (is.null(mf) || !is.matrix(mf) || nrow(mf) == 0L) {
    mf_mean <- setNames(rep(NA_real_, n_mfcc), paste0("mfcc_", seq_len(n_mfcc)))
  } else {
    mf_mean <- colMeans(mf, na.rm = TRUE)
    names(mf_mean) <- paste0("mfcc_", seq_len(n_mfcc))
  }

  # --- Spectral descriptors ---
  sp <- tryCatch(
    .spectral_props(v, sr = sr),
    error = function(e) setNames(c(NA_real_, NA_real_, NA_real_),
                                 c("spec_centroid","spec_bandwidth","spec_flatness"))
  )

  # --- Chroma (12 pitch class energies, normalised to sum to 1) ---
  ch <- tryCatch(
    .chroma_12(v, sr = sr),
    error = function(e) NULL
  )
  if (is.null(ch)) {
    chroma_mean <- setNames(rep(NA_real_, 12L),
                            c("C","C#","D","D#","E","F","F#","G","G#","A","A#","B"))
  } else {
    chroma_mean <- ch
  }

  # --- Tempo (approximate) ---
  # seewave::timer returns a list with elements $s (envelope), $p (peaks),
  # $r (BPM, the number we want), $s.start, $s.end, $first. We extract $r and
  # fall back to NA when it's missing or NA.
  tempo <- tryCatch({
    t <- seewave::timer(v, f = sr, plot = FALSE)
    if (is.list(t) && !is.null(t$r) && length(t$r) >= 1L) {
      as.numeric(t$r[1])
    } else if (is.numeric(t)) {
      as.numeric(t[1])
    } else {
      NA_real_
    }
  }, error = function(e) NA_real_)

  # --- Zero-crossing rate ---
  zcr <- tryCatch(
    as.numeric(seewave::zcr(v, f = sr, wl = 1024, ovlp = 50, plot = FALSE)[2]),
    error = function(e) NA_real_
  )

  c(mf_mean, sp, chroma_mean, tempo = tempo, zcr = zcr)
}

# ---------------------------------------------------------------------------
# Job collection
# ---------------------------------------------------------------------------

#' Build (song_id -> mp3_path) from a catalog JSON file plus an mp3 directory.
#'
#' Each catalog entry may carry an mp3 filename of either shape:
#'   * numeric stem (e.g. "3342319503.mp3")  -> song_id = "3342319503"
#'   * human-readable stem (e.g. "ilem - 白鸟过河滩.mp3") -> song_id = NA,
#'     and the catalog key is treated as the display name.
#'
#' Returns a data.frame with columns (song_id, mp3_path, display_name) so the
#' analysis layer can still group / filter, even when real song_ids are missing.
build_jobs <- function(catalog_path, mp3_dir) {
  if (!file.exists(catalog_path)) {
    stop("catalog not found: ", catalog_path)
  }
  if (!dir.exists(mp3_dir)) {
    stop("mp3 dir not found: ", mp3_dir)
  }
  cat <- fromJSON(catalog_path, simplifyVector = FALSE)
  rows <- list()
  for (key in names(cat)) {
    e <- cat[[key]]
    mp3_file <- e$mp3_file %||% paste0(key, ".mp3")
    mp3_path <- file.path(mp3_dir, mp3_file)
    if (!file.exists(mp3_path)) {
      # Skip silently; the caller logs progress.
      next
    }
    # Use the catalog key as the row identifier when song_id is unknown.
    sid <- e$song_id %||% NA_character_
    if (is.na(sid) || !nzchar(sid)) sid <- NA_character_
    rows[[length(rows) + 1L]] <- data.frame(
      song_id      = sid,
      catalog_key  = key,
      mp3_path     = mp3_path,
      display_name = if (!is.null(e$name) && nzchar(e$name)) e$name else key,
      stringsAsFactors = FALSE
    )
  }
  if (length(rows) == 0L) {
    stop("no catalog entry matched an mp3 file in ", mp3_dir)
  }
  do.call(rbind, rows)
}

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

save_outputs <- function(results, failures, out_dir) {
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  feat_path  <- file.path(out_dir, "song_features.csv")
  fail_path  <- file.path(out_dir, "song_features_failures.csv")

  ok_df <- do.call(rbind, lapply(results, function(r) {
    data.frame(song_id = r$song_id, as.list(r$features), check.names = FALSE)
  }))
  if (file.exists(feat_path)) {
    old <- read.csv(feat_path, stringsAsFactors = FALSE)
    if (ncol(old) == ncol(ok_df) && nrow(old) > 0L) {
      ok_df <- rbind(old, ok_df[!old$song_id %in% ok_df$song_id, ])
    }
    # If the existing file has a malformed header (0 columns), skip the merge
    # and overwrite with the freshly computed rows.
  }
  write.csv(ok_df, feat_path, row.names = FALSE)

  fail_df <- if (length(failures)) {
    do.call(rbind, lapply(failures, function(f) {
      data.frame(song_id = f$song_id, mp3 = f$mp3, reason = f$reason,
                 stringsAsFactors = FALSE)
    }))
  } else data.frame(song_id = character(0), mp3 = character(0), reason = character(0))
  write.csv(fail_df, fail_path, row.names = FALSE)

  list(features = feat_path, failures = fail_path,
       n_ok = nrow(ok_df), n_fail = nrow(fail_df))
}

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

main <- function(argv = NULL) {
  if (is.null(argv)) argv <- commandArgs(trailingOnly = TRUE)

  parse_args <- function(a) {
    out <- list(src = "data/mp3", out = "data/embeddings",
                catalog = "data/songs_catalog.json", n_mfcc = 13L)
    i <- 1L
    while (i <= length(a)) {
      x <- a[[i]]
      if (x %in% c("--src", "-s")) { out$src <- a[[i + 1L]]; i <- i + 2L
      } else if (x %in% c("--out", "-o")) { out$out <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--catalog") { out$catalog <- a[[i + 1L]]; i <- i + 2L
      } else if (x == "--n-mfcc") { out$n_mfcc <- as.integer(a[[i + 1L]]); i <- i + 2L
      } else if (x %in% c("--help", "-h")) {
        cat("usage: Rscript extract_audio_features.R --src DIR --out DIR --catalog FILE [--n-mfcc N]\n")
        quit(status = 0L)
      } else { stop("unknown arg: ", x) }
    }
    out
  }
  args <- parse_args(argv)
  log_info("src=", args$src, " out=", args$out, " catalog=", args$catalog,
           " n_mfcc=", args$n_mfcc)

  jobs <- build_jobs(args$catalog, args$src)
  log_info("found ", nrow(jobs), " mp3 files")

  results  <- list()
  failures <- list()
  for (j in seq_len(nrow(jobs))) {
    sj <- jobs[j, ]
    log_info("[", j, "/", nrow(jobs), "] ", sj$mp3_path)
    feats <- tryCatch(
      compute_features(read_mp3_mono(sj$mp3_path), n_mfcc = args$n_mfcc),
      error = function(e) {
        failures[[length(failures) + 1L]] <<- list(
          song_id = if (is.na(sj$song_id)) sj$catalog_key else sj$song_id,
          mp3     = sj$mp3_path,
          reason  = conditionMessage(e)
        )
        NULL
      }
    )
    if (!is.null(feats)) {
      row_key <- if (is.na(sj$song_id)) sj$catalog_key else sj$song_id
      results[[length(results) + 1L]] <- list(
        song_id     = row_key,
        display_name = sj$display_name,
        features    = feats
      )
    }
  }

  paths <- save_outputs(results, failures, args$out)
  log_info("done: features -> ", paths$features, " (n=", paths$n_ok,
           ") failures -> ", paths$failures, " (n=", paths$n_fail, ")")
  invisible(0L)
}

if (!interactive() && identical(sys.nframe(), 0L)) {
  tryCatch(main(), error = function(e) {
    log_err("fatal: ", conditionMessage(e))
    quit(status = 1L)
  })
}
