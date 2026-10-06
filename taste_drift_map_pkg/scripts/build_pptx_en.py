# -*- coding: utf-8 -*-
"""Build the English "Taste Drift Map" deck.

Starts from the ORIGINAL 16-page (English) presentation.pptx and appends
12 new English pages whose figures are all produced by the R scripts in
r_project/. Design language is copied from the original deck:
  13.33 x 7.5 in; kicker 11.5pt grey; title 27pt #10131A;
  accent bar 0.42x0.07in top-left; footer line #E3E6EB + page number;
  content cards = #F4F5F7 rounded rect + colored side bar.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parent.parent          # 仓库根
FIG = ROOT / "figures"                                 # 由 run_all.R 生成

# 底版 deck（16 页英文模板）。默认放在 docs/ 下；可用命令行参数覆盖：
#     python build_pptx_en.py path/to/template.pptx
import sys
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "template.pptx"
OUT = ROOT / "docs" / "presentation_v3_en.pptx"

# ---- theme (extracted from the original deck) ----
DARK = RGBColor(0x10, 0x13, 0x1A)
GREY = RGBColor(0x6B, 0x72, 0x80)
GREY_L = RGBColor(0xC9, 0xD1, 0xDB)
BG_CARD = RGBColor(0xF4, 0xF5, 0xF7)
LINE = RGBColor(0xE3, 0xE6, 0xEB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1D, 0xB9, 0x54)
PURPLE = RGBColor(0x7C, 0x5C, 0xFF)
CYAN = RGBColor(0x22, 0xB8, 0xD8)
CORAL = RGBColor(0xFF, 0x6B, 0x6B)
RED = RGBColor(0xDC, 0x26, 0x26)
BLUE = RGBColor(0x25, 0x63, 0xEB)
ORANGE = RGBColor(0xF5, 0x9E, 0x0B)
FONT = "Segoe UI"

# ---- numbers verified by the R pipeline (auc_bootstrap.txt / bootstrap_noise.txt) ----
AUC_PT, AUC_LO, AUC_HI = 0.661, 0.591, 0.732
NOISE_LO, NOISE_HI = 2.6, 4.3
FULL_ANGLE = 3.93


def add_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(sl, x, y, w, h, color, round_=False):
    shp = sl.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def text(sl, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         wrap=True, spacing=1.0):
    """runs: (t,sz,b,c) | [(t,sz,b,c),...] | [[(t,...),...], ...]"""
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if isinstance(runs, tuple):
        runs = [[runs]]
    elif isinstance(runs, list) and runs and isinstance(runs[0], tuple):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        for item in para:
            t, sz, b, c = item[0], item[1], item[2], item[3]
            r = p.add_run(); r.text = t
            r.font.size = Pt(sz); r.font.bold = b
            r.font.color.rgb = c; r.font.name = FONT
    return tb


def header(sl, kicker, title, accent):
    rect(sl, 0.62, 0.46, 0.42, 0.07, accent)
    text(sl, 0.62, 0.62, 12.09, 0.28, (kicker, 11.5, True, GREY))
    text(sl, 0.62, 0.88, 12.09, 0.55, (title, 27, True, DARK))


def footer(sl, num):
    rect(sl, 0.62, 6.98, 12.09, 0.012, LINE)
    text(sl, 12.11, 7.05, 0.60, 0.30, (str(num), 9.5, True, GREY))


from PIL import Image


def pic(sl, path, x, y, w, max_h=None):
    """Fit by width; cap height at max_h (scale by height + center horizontally)."""
    with Image.open(str(path)) as im:
        iw, ih = im.size
    h = w * ih / iw
    if max_h and h > max_h:
        h = max_h
        w = h * iw / ih
        x = x + (12.09 - w) / 2
    return sl.shapes.add_picture(str(path), Inches(x), Inches(y),
                                 width=Inches(w), height=Inches(h))


def numbered_card(sl, x, y, w, h, num, accent, title, body, tsize=14.5, bsize=10.5):
    rect(sl, x, y, w, h, BG_CARD, round_=True)
    rect(sl, x, y, 0.90 if h > 1.2 else 0.66, h, accent)
    text(sl, x, y + 0.02, 0.90 if h > 1.2 else 0.66, h,
         (num, 20 if h > 1.2 else 15, True, WHITE),
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(sl, x + 1.08, y + 0.14, w - 1.28, h - 0.28,
         [[(title, tsize, True, DARK)],
          [(body, bsize, False, GREY)]], spacing=1.12)


def main() -> int:
    prs = Presentation(str(SRC))
    n0 = len(prs.slides)
    num = n0

    # =========================================================================
    # S17 Section divider
    # =========================================================================
    s = add_slide(prs); num += 1
    rect(s, 0, 0, 13.333, 7.5, DARK)
    rect(s, 0.62, 3.28, 0.42, 0.07, GREEN)
    text(s, 0.62, 3.45, 12.09, 0.28, ("Part 6  \u00b7  New analysis", 13, True, GREEN))
    text(s, 0.62, 3.80, 12.09, 1.0, ("Taste Drift Map", 52, True, WHITE))
    text(s, 0.62, 4.85, 12.09, 0.4,
         ("CLAP vectors of 374 charted songs - two questions, three answers",
          24, False, GREY_L))

    # =========================================================================
    # S18 Data & method
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 DATA", "What data we used, and how it became vectors", PURPLE)
    numbered_card(s, 0.62, 1.75, 12.09, 1.05, "01", GREEN, "Two charts",
                  "QQ Music monthly Top10, 730 entries (2018.8-2024.12)  +  NetEase Cloud Music annual song chart, 63 entries (2018-2024)",
                  14, 10.5)
    numbered_card(s, 0.62, 2.95, 12.09, 1.05, "02", CYAN, "Matched to local audio",
                  "Normalized-title matching against local MP3s: QQ Music hit 429 entries / 319 songs (58.8%), NetEase 60 / 55 (95.2%)",
                  14, 10.5)
    numbered_card(s, 0.62, 4.15, 12.09, 1.05, "03", PURPLE, "Each song \u2192 a 512-dim vector",
                  "CLAP (laion/clap-htsat-unfused): 48 kHz mono \u2192 10 s windows, 10 s hop \u2192 log-Mel spectrogram \u2192 HTS-AT encoder \u2192 window average \u2192 L2",
                  14, 10.5)
    numbered_card(s, 0.62, 5.35, 12.09, 1.05, "04", CORAL, "374 unique songs, one shared space",
                  "Every vector lives in the same 512-dim space, so platforms and years are directly comparable. GPU vectorization: 4.7 min, 0 failures.",
                  14, 10.5)
    footer(s, num)

    # =========================================================================
    # S19 Chain 1: waveform & windowing
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 METHOD", "How a song becomes a vector \u00b7 \u2460 waveform & windowing", CYAN)
    text(s, 0.62, 1.52, 12.09, 0.35,
         [("Sample song: Snow Distance - Capper / Luo Yan  (NetEase annual chart #1, 2023)",
           12.5, True, GREY)])
    pic(s, FIG / "chain_1_waveform.png", 0.62, 2.05, 12.09, max_h=3.55)
    text(s, 0.62, 5.75, 12.09, 1.0,
         [[("Why cut 10-second windows?", 13.5, True, DARK)],
          [("CLAP's audio encoder only accepts fixed-length input (~10 s). A 166 s song is cut into 17 "
            "non-overlapping windows; each window is encoded separately and averaged - so every section "
            "of the song is seen, not just the chorus.", 11, False, GREY)]], spacing=1.15)
    footer(s, num)

    # =========================================================================
    # S20 Chain 2: spectrogram
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 METHOD", "How a song becomes a vector \u00b7 \u2461 waveform to spectrogram", CYAN)
    pic(s, FIG / "chain_2_spectrogram.png", 0.62, 1.60, 12.09, max_h=4.25)
    text(s, 0.62, 6.05, 12.09, 0.8,
         [[("The log-Mel spectrogram is the model's real input.", 13.5, True, DARK)],
          [("It warps linear frequency onto a scale that mimics the human ear (low-freq dense, high-freq sparse) "
            "and takes the log of magnitudes - that is how ears hear. From here on the model never sees the waveform again.",
            11, False, GREY)]], spacing=1.15)
    footer(s, num)

    # =========================================================================
    # S21 Chain 3: encode & pool
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 METHOD", "How a song becomes a vector \u00b7 \u2462 encode & pool", CYAN)
    pic(s, FIG / "chain_3_vector.png", 0.62, 1.58, 12.09, max_h=4.55)
    text(s, 0.62, 6.28, 12.09, 0.6,
         [[("17 window vectors \u2192 average \u2192 L2 normalize \u2192 one song = one point in 512-dim space.",
            13.5, True, DARK)],
          [("Window-to-window cosine averages 0.887 - sections of the same song are genuinely similar, "
            "so averaging is safe.", 11, False, GREY)]], spacing=1.15)
    footer(s, num)

    # =========================================================================
    # S22 Chain 4: similarity = angle
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 METHOD", "How a song becomes a vector \u00b7 \u2463 similarity = angle", CYAN)
    pic(s, FIG / "chain_4_similarity.png", 0.62, 1.60, 12.09, max_h=4.05)
    text(s, 0.62, 5.85, 12.09, 1.0,
         [[("Cosine only measures direction, not length.", 13.5, True, DARK)],
          [("Note the histogram: every library song sits at 0.7-0.9 (mean 0.830), not scattered around 0 - the "
            "\u201cnarrow cone effect\u201d of contrastive audio models. It does not hurt ranking, but \u201csimilarity 0.85\u201d "
            "never means \u201cthe same song\u201d; only relative differences matter.", 11, False, GREY)]],
         spacing=1.15)
    footer(s, num)

    # =========================================================================
    # S23 Map overview
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 RESULT", "The map: both platforms share one region", GREEN)
    pic(s, FIG / "map_overview.png", 0.62, 1.62, 12.09, max_h=4.45)
    text(s, 0.62, 6.25, 12.09, 0.6,
         [[("349 of 360 unique titles chart on one platform only,",
           13.5, True, DARK),
           (" yet in vector space they all mix together - chart rosters differ, "
            "the style distribution of what gets picked does not.", 13.5, True, DARK)]],
         spacing=1.15)
    footer(s, num)

    # =========================================================================
    # S24 Q1 platform difference
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 FINDING 1", "Platform difference: averages identical, song mix different", CORAL)
    pic(s, FIG / "map_platform.png", 0.62, 1.58, 12.09, max_h=4.42)
    text(s, 0.62, 6.15, 12.09, 0.75,
         [[("Q1 answer:  ", 13, True, GREEN),
           (f"average taste is indistinguishable (full-period centroid angle {FULL_ANGLE}\u00b0, inside the "
            f"bootstrap noise band), but single songs are separable (AUC {AUC_PT:.2f}, 95% CI "
            f"[{AUC_LO:.2f}, {AUC_HI:.2f}]). Same-year angles (7-9\u00b0) exceed the full-period angle: "
            "the difference comes from year composition, not platform style.", 11.5, False, GREY)]],
         spacing=1.18)
    footer(s, num)

    # =========================================================================
    # S25 Q2 annual trajectory
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 FINDING 2", "How taste changes: vibration in place, no one-way drift", CORAL)
    pic(s, FIG / "map_trajectory.png", 0.62, 1.58, 12.09, max_h=4.48)
    text(s, 0.62, 6.20, 12.09, 0.7,
         [[("Q2 answer:  ", 13, True, CORAL),
           ("total drift 2018\u21922023 is only 4.1\u00b0 - smaller than a single year's swing (4.6\u00b0). Most year-over-year "
            f"steps sit inside the bootstrap noise band ({NOISE_LO}-{NOISE_HI}\u00b0). NetEase 2018/19 jumps (21.6\u00b0/15.2\u00b0) "
            "are 2 songs compared to 2 songs - not interpretable.", 11.5, False, GREY)]],
         spacing=1.18)
    footer(s, num)

    # =========================================================================
    # S26 Monthly granularity
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 RESULT", "Monthly granularity: fluctuation is the norm, trend is absent", GREEN)
    pic(s, FIG / "map_monthly.png", 0.62, 1.62, 12.09, max_h=4.58)
    text(s, 0.62, 6.40, 12.09, 0.5,
         [("Monthly centroids swing 8-23.5\u00b0 against 2018-08, while yearly centroids (stars) hug the 10\u00b0 line - "
           "the playlist keeps rotating, the mix of styles does not.", 12.5, True, DARK)])
    footer(s, num)

    # =========================================================================
    # S27 Data boundaries
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 BOUNDARIES", "What this analysis can and cannot answer", PURPLE)
    pic(s, FIG / "map_coverage.png", 0.62, 1.58, 12.09, max_h=4.37)
    text(s, 0.62, 6.10, 12.09, 0.85,
         [[("Three limitations we must state:", 13, True, DARK)],
          [("\u2460 QQ 2024 H2 audio is missing locally (5/100 chart entries \u2192 3 unique songs), so that year's "
            "10.6\u00b0 jump is sample collapse;  \u2461 NetEase officially publishes only 1-2 songs for 2018/2019 - no "
            "yearly centroid possible;  \u2462 NetEase has no monthly chart, so monthly fluctuation can only be "
            "measured on QQ.", 11, False, GREY)]], spacing=1.18)
    footer(s, num)

    # =========================================================================
    # S28 Summary: three questions, three answers
    # =========================================================================
    s = add_slide(prs); num += 1
    header(s, "TASTE MAP \u00b7 SUMMARY", "Three questions, three answers", GREEN)
    numbered_card(s, 0.62, 1.62, 12.09, 1.35, "Q1", GREEN,
                  "Platform difference - averages identical, mixes different",
                  f"Full-period centroid angle {FULL_ANGLE}\u00b0 (noise band 2.6-4.3\u00b0) \u2192 no real difference in average taste; "
                  f"per-song AUC {AUC_PT:.2f} [{AUC_LO:.2f}, {AUC_HI:.2f}] \u2192 which songs chart is systematically different; "
                  "same-year angles 7-9\u00b0 \u2192 difference comes from year composition, not platform style.",
                  14, 10.5)
    numbered_card(s, 0.62, 3.15, 12.09, 1.35, "Q2", CORAL,
                  "Taste change - vibration in place, no one-way migration",
                  "QQ Music 2018-2023 total drift 4.1\u00b0 (smaller than one year's swing); monthly jumps 8-23.5\u00b0; "
                  "NetEase 2020+ oscillates 7-10\u00b0 yearly. Change happens in specific songs (rosters rotate almost "
                  "completely), not in the average style.",
                  14, 10.5)
    numbered_card(s, 0.62, 4.68, 12.09, 1.35, "Q3", CYAN,
                  "Method - one song = one point on the 512-dim unit sphere",
                  "10 s windows \u2192 log-Mel spectrogram \u2192 HTS-AT encoder \u2192 window average \u2192 L2 normalize. "
                  "Similarity = cosine (angle). All 374 songs share one space, so platforms and years are directly comparable.",
                  14, 10.5)
    text(s, 0.62, 6.30, 12.09, 0.4,
         [("Reproducible pipeline: swap in a new chart CSV + audio \u2192 export_for_r.py \u2192 R scripts (r_project/) "
           "regenerate every figure.", 11, False, GREY)])
    footer(s, num)

    prs.save(str(OUT))
    print(f"Saved {OUT.name}: original {n0} pages + 12 new = {len(prs.slides)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
