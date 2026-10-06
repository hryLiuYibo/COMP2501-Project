# Findings — with the data behind each number

Every number below comes from a sample whose boundaries are stated. **Conclusions
always carry their sample size and confidence interval**; nothing is inferred
beyond what the data supports. All statistics regenerate with
`Rscript r_project/run_all.R`; the data dictionary is in
[`r_project/README.md`](r_project/README.md).

## Data boundaries — read this first

| | QQ Music | NetEase Cloud Music |
|---|---|---|
| chart records | 730 (2018.8–2024.12, monthly Top-10) | 80 raw (overall / Mandarin / genre lists, 2018–2024); **63** after (year × song) dedup |
| matched to local audio | 429 records | 60 records |
| unique songs after matching | 319 | 55 |
| chart coverage | 58.8% of records (64.2% of unique titles) | 95.2% of records (94.9% of unique titles) |
| time granularity | **monthly** | **yearly** (only annual charts are published) |
| critical gap | **almost no audio for 2024 H2** (2024 whole-year: 5 matches → 3 unique songs) | only 2 songs each for 2018 / 2019 |

Matching rule: normalize titles (full-width forms, brackets, `feat.`, punctuation)
and accept **exact** equality; "contains" matches are accepted only if the artist
also agrees, otherwise discarded. The remaining 17 edge cases were adjudicated by
hand (see `MANUAL_DECISIONS` in `scripts/build_matches.py`).

---

## Q1 — platform difference: centroids nearly coincide, individuals separable

| metric | value | reading |
|---|---|---|
| full-period centroid angle | **3.93°** (cosine 0.9977) | average taste is nearly identical |
| single-song separability (AUC) | **0.661**, 95% CI [0.591, 0.732] (song-level bootstrap, B = 2000) | clearly above 0.5, far from 1.0 |
| same-year centroid angle | 2020: 9.13° / 2021: 7.17° / 2022: 7.90° / 2023: 8.58° | controlling for year makes the difference **larger** |
| within-library mean pairwise cosine | QQ 0.8599 / NetEase 0.8660 | comparable internal concentration |
| deviation from the global mean | QQ 1.9–10.7° / NetEase 5.5–8.1° | NetEase sits further from the "market centre" |

**Interpretation.** The two platforms publish almost identical *average* taste
(3.93° is negligible on CLAP's narrow-cone scale — the year-to-year bootstrap
uncertainty alone is 2.6–4.3°). But **individual songs are separable**
(AUC 0.66, CI does not cross 0.5): *which* songs chart differs systematically.
Because same-year angles (7–9°) exceed the full-period angle (3.93°), that
difference comes mainly from **year composition** (QQ is heavy on 2019–2023,
NetEase concentrates on 2020–2024), not from an inherent platform style.

> The 2024 same-year angle (12.80°) is **not** used as a finding: it rests on
> n = 3 QQ songs vs n = 10 NetEase.

---

## Q2 — how taste moves: oscillation around the mean, no one-way drift

### QQ Music (monthly granularity, 429 records / 319 songs)

Adjacent-year centroid angle:
`2018→2019 3.82°` · `2019→2020 2.99°` · `2020→2021 2.94°` · `2021→2022 4.62°` ·
`2022→2023 4.36°`

- **No monotonic drift.** Adjacent-year angles bounce between 2.9° and 4.6°;
  the **2018 → 2023 total span is only 4.14°** — smaller than a single year's
  swing (4.62°). Over six years the centroid essentially did not move.
- **Monthly fluctuation dwarfs the annual drift**: monthly centroid angles
  against the 2018-08 baseline swing across **8–23.5°**, completely burying
  year-over-year differences.
- **Robustness**: bootstrap uncertainty of the yearly centroids (300 resamples
  per year, song level; mean angle between resampled and full centroid) is
  **2.6–4.3°** — the *same order of magnitude* as the year-to-year drift, so
  most of that drift is noise. 2018 has the largest uncertainty (4.26°, n = 33).
- **The 2024 10.59° jump is unusable**: 2024 has only **3 unique songs**, below
  the minimum sample for a bootstrap (n ≥ 4), so no uncertainty is reported.
  Those 3 songs sit 18.0–22.5° from the 2023 centroid. This is **sample
  collapse**, not a "2024 taste shift".
- Within-library dispersion 0.836–0.876, no trend.
- Chinese-title share 73.7% → 92% → 84.6%, holding at 85–92% long-term; no
  structural break.

### NetEase Cloud Music (yearly granularity, 60 records / 55 songs)

Adjacent-year centroid angle:
`2018→2019 21.56°` · `2019→2020 15.17°` · `2020→2021 7.21°` · `2021→2022 9.71°` ·
`2022→2023 8.51°` · `2023→2024 9.76°`

- The end-to-end span (2018 → 2024) is 16.29°, **larger** than QQ's — but 2018
  and 2019 have only 2 songs each, so that 21.56° is 2 songs against 2 songs and
  **cannot support any conclusion**.
- From 2020 onward (≥10 songs/year): `7.21° → 9.71° → 8.51° → 9.76°` — again
  **oscillation around the mean**, no one-way trend.
- Within-library dispersion 0.847–0.877, no trend.

**Conclusion.** Neither platform shows one-way taste drift over 2018–2024. The
yearly centroid movement is the same order as its own statistical uncertainty:
they are "shaking inside the same small region". Real change happens at the
level of **individual songs** (chart rosters rotate almost completely), not in
the **average style**.

---

## Q3 — how a song becomes a vector (the principle chain)

Probe song: ***雪 Distance* — Capper / Luo Yan** (NetEase 2023 annual #1).

1. Decode the audio → 48 kHz mono waveform
2. Cut into **10 s windows, 10 s hop** (non-overlapping, hence reproducible)
3. Each window passes a learnable **log-Mel spectrogram** front end — this is
   what the model actually "sees"
4. The **HTS-AT** audio encoder (hierarchical transformer with time-frequency
   tokenization) encodes each window
5. Each window → 512 dims → average over all windows → L2-normalize
6. One song = **one point on the 512-d unit sphere**; similarity = cosine of the
   angle between two points

Window-to-window cosine for the probe song averages **0.887** (17 windows), so
pooling by averaging is safe. Across the whole library the mean pairwise cosine
is **0.831** — the **narrow cone effect**: all audio vectors crowd into a sharp
cone. It does not hurt ranking, but an absolute "similarity 0.85" is meaningless;
only relative gaps carry signal.

---

## Reproduce

```bash
Rscript r_project/run_all.R        # figures + statistics, no audio needed
```

Authoritative values are written to
[`r_project/auc_bootstrap.txt`](r_project/auc_bootstrap.txt) and
[`r_project/bootstrap_noise.txt`](r_project/bootstrap_noise.txt).
