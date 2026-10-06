# -*- coding: utf-8 -*-
"""Merge the teammate's chart-metadata deck (slides(3).pptx content) into the
presentation_v3_en.pptx design language -> presentation_final.pptx (33 pages).

Design source : presentation_v3_en.pptx  (16 template pages + 12 taste-map pages)
Content source: slides(3).pptx (teammate, HKU COMP2501) + our CLAP extension

Final structure (33 pages, ~18 min):
   1 T1  title                      18 T10 three changepoints
   2 T2  agenda (5 parts)           19 N4  yearly offset (native heatmap table)
   3 T3  Part 1 section             20 N5  cross-chart correlation
   4 T4  the story                  21 N6  genre drift (redrawn fig)
   5 T5  data science questions     22 N7  cross-region
   6 N1  why important              23 O23 taste map overview
   7 N2  existing works             24 O24 finding 1
   8 T6  Part 2 section             25 O25 finding 2
   9 T7  data available             26 O26 monthly granularity
  10 T8  pipeline & toolchain       27 T11 Part 4 section
  11 N3  difficulties               28 T12 key insights
  12 O18 taste-map data->vectors    29 O27 limitations
  13 O19 chain 1 waveform           30 T14 Part 5 section
  14 O20 chain 2 spectrogram        31 N8  conclusion & future works
  15 O21 chain 3 encode & pool      32 N9  references
  16 O22 chain 4 similarity         33 T16 thank you
  17 T9  Part 3 section
Deleted: T13, T15 (empty template pages), O17 (part-6 divider), O28 (Q1/Q2/Q3
summary - numbering clashes with the teammate's Q1/Q2; answers live in N8).
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent          # 仓库根
IMG = ROOT / "docs" / "assets"                         # 从队友 deck 抽出的 2 张图
ASSETS = ROOT / "data" / "interim"                     # 运行期生成的图
ASSETS.mkdir(parents=True, exist_ok=True)

# 底版 deck：build_pptx_en.py 的产物（16 页模板 + 12 页 taste map）
import sys
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "presentation_v3_en.pptx"
# 队友的 deck（内容来源），仅用于对照，不参与构建时可不存在
TEAM_DECK = ROOT / "docs" / "team_slides.pptx"
OUT = ROOT / "docs" / "presentation_final.pptx"

# ---- theme (identical to build_pptx_en.py) ----
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
LEFT, RIGHT, CENTER = PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.CENTER
MID, TOP = MSO_ANCHOR.MIDDLE, MSO_ANCHOR.TOP

AUC_PT = 0.661

# =====================================================================
# generic helpers
# =====================================================================

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


def _norm_runs(runs):
    """runs -> list of paragraphs, each a list of (t, sz, b, c)."""
    if isinstance(runs, tuple):
        return [[runs]]
    if runs and isinstance(runs[0], tuple):
        return [runs]
    return [list(p) for p in runs]


def text(sl, x, y, w, h, runs, align=LEFT, anchor=TOP, wrap=True, spacing=1.0):
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    write_tf(tf, runs, align, spacing)
    return tb


def write_tf(tf, runs, align, spacing):
    for i, para in enumerate(_norm_runs(runs)):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        for item in para:
            r = p.add_run(); r.text = item[0]
            r.font.size = Pt(item[1]); r.font.bold = item[2]
            r.font.color.rgb = item[3]; r.font.name = FONT


def find(sl, x, y, tol=0.06, wmax=None):
    """Locate a shape by top-left position (inches)."""
    for sh in sl.shapes:
        try:
            if abs(sh.left / 914400 - x) < tol and abs(sh.top / 914400 - y) < tol:
                if wmax is None or sh.width / 914400 <= wmax:
                    return sh
        except Exception:
            continue
    return None


def rewrite(sh, runs_or_paras, align=LEFT, spacing=1.15):
    """Replace the whole text of an existing shape (same convention as text())."""
    tf = sh.text_frame
    tf.clear()
    write_tf(tf, runs_or_paras, align, spacing)


def rewrite_mixed(sh, spec):
    """spec: [(runs, align_or_None, spacing_or_None), ...]"""
    tf = sh.text_frame
    tf.clear()
    for i, (runs, al, sp) in enumerate(spec):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if al is not None:
            p.alignment = al
        if sp is not None:
            p.line_spacing = sp
        for item in runs:
            r = p.add_run(); r.text = item[0]
            r.font.size = Pt(item[1]); r.font.bold = item[2]
            r.font.color.rgb = item[3]; r.font.name = FONT


def header(sl, kicker, title, accent):
    rect(sl, 0.62, 0.46, 0.42, 0.07, accent)
    text(sl, 0.62, 0.62, 12.09, 0.28, (kicker, 11.5, True, GREY), spacing=1.15)
    text(sl, 0.62, 0.88, 12.09, 0.55, (title, 27, True, DARK), spacing=1.15)


def footer(sl):
    rect(sl, 0.62, 6.98, 12.09, 0.012, LINE)
    text(sl, 12.11, 7.05, 0.60, 0.30, ("0", 9.5, True, GREY), align=RIGHT)


def pic(sl, path, x, y, w, max_h=None):
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
         (num, 20 if h > 1.2 else 15, True, WHITE), align=CENTER, anchor=MID)
    text(sl, x + 1.08, y + 0.14, w - 1.28, h - 0.28,
         [[(title, tsize, True, DARK)], [(body, bsize, False, GREY)]], spacing=1.12)


def quote_card(sl, x, y, w, h, accent, runs, pad=0.30):
    rect(sl, x, y, w, h, BG_CARD, round_=True)
    rect(sl, x, y, 0.07, h, accent)
    text(sl, x + pad, y + 0.08, w - pad - 0.22, h - 0.16, runs, anchor=MID, spacing=1.15)


def step_card(sl, x, y, w, h, num, accent, title, body):
    rect(sl, x, y, w, h, BG_CARD, round_=True)
    rect(sl, x, y, w, 0.07, accent)
    text(sl, x + 0.20, y + 0.20, w - 0.40, 0.28, (num, 11, True, accent))
    text(sl, x + 0.20, y + 0.52, w - 0.40, h - 0.72,
         [[(title, 13, True, DARK)], [(body, 10, False, GREY)]], spacing=1.15)


def event_card(sl, x, y, w, h, accent, year, title, body):
    rect(sl, x, y, w, h, BG_CARD, round_=True)
    rect(sl, x, y, w, 0.07, accent)
    text(sl, x + 0.22, y + 0.20, w - 0.44, 0.42, (year, 21, True, accent))
    text(sl, x + 0.22, y + 0.70, w - 0.44, 0.30, (title, 13, True, DARK))
    text(sl, x + 0.22, y + 1.06, w - 0.44, h - 1.24, (body, 10.5, False, GREY),
         spacing=1.15)


def blend(c1, c2, t):
    return RGBColor(*[int(round(a + (b - a) * t)) for a, b in zip(c1, c2)])


def set_cell(cell, runs, fill, align=CENTER):
    cell.fill.solid(); cell.fill.fore_color.rgb = fill
    cell.vertical_anchor = MID
    cell.margin_left = cell.margin_right = Inches(0.07)
    cell.margin_top = cell.margin_bottom = Inches(0.02)
    tf = cell.text_frame
    tf.word_wrap = True
    write_tf(tf, runs, align, 1.05)


def make_table(sl, x, y, col_ws, row_hs):
    gf = sl.shapes.add_table(len(row_hs), len(col_ws), Inches(x), Inches(y),
                             Inches(sum(col_ws)), Inches(sum(row_hs)))
    tbl = gf.table
    tbl.first_row = False
    tbl.horz_banding = False
    for i, w in enumerate(col_ws):
        tbl.columns[i].width = Inches(w)
    for j, h in enumerate(row_hs):
        tbl.rows[j].height = Inches(h)
    return tbl


def set_kicker(sl, kicker, sp=1.15):
    rewrite(find(sl, 0.62, 0.62), (kicker, 11.5, True, GREY), spacing=sp)


def set_accent(sl, color):
    sh = find(sl, 0.62, 0.46, wmax=0.6)
    sh.fill.solid(); sh.fill.fore_color.rgb = color


def delete_slide(prs, slide):
    id_lst = prs.slides._sldIdLst
    for sldId in list(id_lst):
        if prs.part.related_part(sldId.rId) is slide.part:
            prs.part.drop_rel(sldId.rId)
            id_lst.remove(sldId)
            return
    raise RuntimeError("slide not found for deletion")


def reorder(prs, ordered):
    id_lst = prs.slides._sldIdLst
    m = {}
    for sldId in list(id_lst):
        m[prs.part.related_part(sldId.rId)] = sldId
    for sldId in list(id_lst):
        id_lst.remove(sldId)
    for sl in ordered:
        id_lst.append(m[sl.part])


def renumber(order):
    for pos, sl in enumerate(order, 1):
        sh = find(sl, 12.11, 7.05, wmax=0.75)
        if sh is not None and sh.has_text_frame:
            rewrite(sh, (str(pos), 9.5, True, GREY), align=RIGHT, spacing=1.15)


# =====================================================================
# part A - genre drift figure (matplotlib, deck palette)
# =====================================================================

def make_genre_fig(out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Segoe UI"]

    years = [2020, 2021, 2022, 2023, 2024]
    series = [("rap", [39, 41, 40, 43, 36], "#DC2626"),
              ("edm", [27, 33, 39, 40, 41], "#2563EB"),
              ("guofeng", [34, 26, 21, 17, 24], "#1DB954")]
    fig, ax = plt.subplots(figsize=(7.4, 4.15), dpi=200)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")

    ax.axvline(2022, color="#9CA3AF", lw=1.2, ls=(0, (4, 3)), zorder=1)
    ax.text(2022, 50.5, "2022 platform split", ha="center", va="top",
            fontsize=9, color="#6B7280")

    for name, ys, c in series:
        ax.plot(years, ys, color=c, lw=2.6, marker="o", ms=6, zorder=3,
                markerfacecolor="white", markeredgewidth=2.2)
        ax.annotate(f"{name}  {ys[-1]}%", xy=(2024, ys[-1]), xytext=(2024.12, ys[-1]),
                    fontsize=11.5, fontweight="bold", color=c, va="center")
        for xv, yv in [(years[0], ys[0]), (years[-1], ys[-1])]:
            ax.annotate(f"{yv}%", xy=(xv, yv), xytext=(0, -14),
                        textcoords="offset points", ha="center",
                        fontsize=8.5, color=c)

    ax.set_xlim(2019.7, 2025.45)
    ax.set_ylim(12, 52)
    ax.set_xticks(years)
    ax.set_yticks([20, 30, 40, 50])
    ax.set_yticklabels(["20%", "30%", "40%", "50%"])
    ax.tick_params(colors="#4B5563", labelsize=10, length=0)
    ax.grid(axis="y", color="#E5E7EB", lw=0.9, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#D1D5DB")
    ax.set_ylabel("share of genre-tagged chart entries", fontsize=10.5, color="#4B5563")
    fig.tight_layout(pad=0.6)
    fig.savefig(str(out_path), facecolor="white")
    plt.close(fig)


# =====================================================================
# part B - template page edits
# =====================================================================

def edit_title(sl):
    b = find(sl, 0.77, 1.55)
    rewrite(b, [[("Listen to the Long Now", 52, True, WHITE)],
                [("Chinese Chart – Listener Behaviour Across Years", 24, False, GREY_L)],
                [("Seven years of chart metadata  ·  audio embeddings of 374 charted songs",
                  15, False, GREY)]], spacing=1.05)
    b = find(sl, 0.77, 5.85)
    rewrite_mixed(b, [
        ([("Presented by  ", 12, False, GREY),
          ("Jiang Chuyang (3036589703)  ·  Liu Yibo (3036589636)", 12, True, WHITE)],
         LEFT, 1.15),
        ([("HKU COMP2501 · Section 1SH   ·   October 2026", 12, True, WHITE)],
         RIGHT, 1.15)])


def edit_agenda(sl):
    descs = [
        (1.97, 2.02, "Project Background",
         "The story, the questions, why it matters, prior work"),
        (1.97, 3.01, "Method and Pipeline",
         "From chart scrapes to CLAP audio vectors"),
        (1.97, 4.00, "Data Analysis",
         "Changepoints, genre drift, cross-region — and the taste map"),
        (1.97, 4.69, "Insights & Limitations",
         "What we learned — and what we cannot claim"),
        (1.97, 5.98, "Conclusion",
         "Answers, future works, references"),
    ]
    for x, y, name, desc in descs:
        sh = find(sl, x, y)
        rewrite(sh, [(name, 15, True, DARK), ("      " + desc, 15, False, GREY)],
                spacing=1.0)


def edit_story(sl):
    set_kicker(sl, "PROJECT BACKGROUND")
    rewrite(find(sl, 0.62, 0.88), ("The story: 2018–2024", 27, True, DARK))
    quote_card(sl, 0.62, 1.62, 12.09, 0.90, GREEN,
               [("Between 2018 and 2024, did Chinese mainstream-music chart-listener "
                 "behaviour drift in measurable ways?", 15, True, DARK)])
    cards = [
        (0.62, CYAN, "2019", "Douyin takeover",
         "Short-video feeds become a hit-making machine; QQ launches the Douyin Hit "
         "chart (topId 60) as Douyin reaches ~400M DAU."),
        (4.75, CORAL, "2020", "COVID-19 stay-at-home",
         "Nationwide lockdown (Jan–Apr); TikTok passes 2B downloads. Chart activity "
         "contracts, then surges after the lockdown."),
        (8.88, PURPLE, "2022", "Ecosystem split",
         "QQ launches the Guofeng Hot Songs chart (topId 65); post-COVID, platform "
         "and genre structures reorganise."),
    ]
    for x, ac, yr, ti, bo in cards:
        event_card(sl, x, 2.72, 3.83, 2.20, ac, yr, ti, bo)
    quote_card(sl, 0.62, 5.15, 12.09, 1.35, GREEN,
               [("Two lenses, one question.  ", 13, True, DARK),
                ("Chart metadata — rotation speed, weekly unique songs, cross-chart "
                 "correlation.  Audio embeddings — what the picked songs actually sound "
                 "like.  Can we find statistically significant changepoints, and do they "
                 "line up with these three events?", 11.5, False, GREY)])


def edit_questions(sl):
    set_kicker(sl, "PROJECT BACKGROUND")
    rewrite(find(sl, 0.62, 0.88), ("Data science questions", 27, True, DARK))
    cards = [
        (1.70, GREEN, "Q1", "Regime shifts in QQ chart behaviour",
         "Across 2018–2024, do QQ Music's seven public weekly toplists (~137,000 "
         "song-week rows) show statistically significant regime shifts — rotation speed, "
         "weekly unique-song count, cross-chart correlation — and which years mark them?"),
        (3.27, CYAN, "Q2", "Platform-conditional or market-wide?",
         "On the same day, do catalogue-freshness and star-concentration profiles of QQ, "
         "NetEase, Apple Music CN and Apple Music US diverge in a way that separates "
         "platform-conditional from market-wide behaviour?"),
        (4.84, CORAL, "Q3", "Does the audio drift too?  (our extension)",
         "Do CLAP embeddings of the charted songs themselves drift across years — and do "
         "the two Chinese platforms pick songs that sound different, or just different "
         "songs?"),
    ]
    for y, ac, num, ti, bo in cards:
        numbered_card(sl, 0.62, y, 12.09, 1.42, num, ac, ti, bo, 14, 10.5)
    text(sl, 0.62, 6.42, 12.09, 0.35,
         [("Q1–Q2 are answered from chart metadata; Q3 is the audio-embedding lens — "
           "listed as future work in the first draft, delivered here.", 11, False, GREY)])


def edit_part_section(sl, subtitle):
    b = find(sl, 0.77, 1.55)
    paras = b.text_frame.paragraphs
    part_no = paras[1].runs[0].text if len(paras) > 1 and paras[1].runs else "Part"
    part_name = paras[2].runs[0].text if len(paras) > 2 and paras[2].runs else ""
    rewrite(b, [[(" ", 13, True, GREEN)],
                [(part_no, 52, True, WHITE)],
                [(part_name, 52, True, WHITE)],
                [(subtitle, 24, False, GREY_L)]], spacing=1.0)


def edit_data_available(sl):
    set_kicker(sl, "METHOD AND PIPELINE")
    rewrite(find(sl, 0.62, 0.88), ("Data available", 27, True, DARK))
    rows = [
        (2.00, "QQ Music — 7 weekly toplists",
         "2018W30–2024W52, ~137,000 song-week rows. Public endpoint u.y.qq.com (same as "
         "the web client), no login; JSON cache + long-format CSV."),
        (2.98, "NetEase Cloud Music — current snapshot",
         "Top-200 from music.163.com (public). No historical weekly endpoint exists."),
        (3.96, "Apple Music CN + US — current snapshots",
         "Top-50 each, official RSS (rss.applemarketingtools.com) — same-day "
         "cross-platform comparison."),
        (4.94, "Local audio — manually downloaded & post-processed",
         "Charted songs collected as MP3s manually, then post-processed (decrypted / "
         "converted to standard MP3) and matched by normalized title: QQ 429 entries / "
         "319 songs (58.8%), NetEase 60 / 55 (95.2%)."),
        (5.92, "Derived data — all computed by us",
         "CLAP 512-d embeddings (374 songs), yearly / monthly centroids, R analysis "
         "database (22 CSVs) — every figure reproducible end-to-end."),
    ]
    for y, ti, bo in rows:
        text(sl, 1.70, y + 0.03, 10.95, 0.82,
             [[(ti, 13.5, True, DARK)], [(bo, 10.5, False, GREY)]],
             anchor=MID, spacing=1.1)


def edit_pipeline(sl):
    set_kicker(sl, "METHOD AND PIPELINE")
    rewrite(find(sl, 0.62, 0.88), ("Pipeline, toolchain & reproducibility", 27, True, DARK))
    cards = [
        (0.62, GREEN, "01", "Fetch — Python",
         "POST u.y.qq.com musicu.fcg for 7 topIds × ~340 weekly issues → JSON cache + "
         "long CSV. Snapshot collectors: NetEase top-200, Apple CN/US top-50."),
        (3.70, CYAN, "02", "Clean & aggregate — R",
         "01_clean.R builds the song-year table: 137K song-week rows → 22,000+ "
         "(song, year) rows, version-normalised, genre-tagged."),
        (6.78, PURPLE, "03", "Analyse — R",
         "Changepoint (BIC + permutation), yearly offset, cross-chart correlation, genre "
         "drift, cross-region, LOF outliers, COVID features (scripts 02–17)."),
        (9.86, CORAL, "04", "Audio branch — Python + R",
         "CLAP vectorization on GPU — 374 songs in 4.7 min, 0 failures → export_for_r.py "
         "→ r_project/: 9 R scripts regenerate every taste-map figure."),
    ]
    for x, ac, num, ti, bo in cards:
        step_card(sl, x, 1.62, 2.85, 3.30, num, ac, ti, bo)
    rect(sl, 0.62, 5.15, 12.09, 1.50, DARK)
    text(sl, 0.92, 5.15, 11.50, 1.50,
         [[("TOOLCHAIN & REPRODUCIBILITY", 10.5, True, GREEN)],
          [("Python 3.13.7 (fetch, CLAP, GPU)   ·   R 4.2.3 + renv (69 packages locked)   "
            "·   pandoc 3.1.13   ·   CLAP laion/clap-htsat-unfused", 12, False, GREY_L)],
          [("renv::restore() → run the scripts in order → every figure and number "
            "regenerates. Chart endpoints are public; audio stays local.",
            10.5, False, GREY_L)]], anchor=MID, spacing=1.3)


def edit_changepoints(sl):
    set_kicker(sl, "DATA ANALYSIS")
    rewrite(find(sl, 0.62, 0.88), ("Three changepoints — all p < 0.001", 27, True, DARK))
    tbl = make_table(sl, 0.62, 1.66, [1.05, 4.85], [0.44, 0.78, 0.78, 0.78])
    set_cell(tbl.cell(0, 0), ("Year", 11, True, WHITE), DARK, LEFT)
    set_cell(tbl.cell(0, 1), ("Real-world event", 11, True, WHITE), DARK, LEFT)
    events = [
        ("2019", "Douyin reaches ~400M DAU; QQ launches the Douyin Hit chart (topId 60)"),
        ("2020", "COVID-19 nationwide stay-at-home (Jan–Apr); TikTok passes 2B downloads"),
        ("2022", "QQ launches the Guofeng Hot Songs chart (topId 65); post-COVID platform split"),
    ]
    for r, (yr, ev) in enumerate(events, 1):
        set_cell(tbl.cell(r, 0), (yr, 11.5, True, DARK), BG_CARD, LEFT)
        set_cell(tbl.cell(r, 1), (ev, 10.5, False, DARK), WHITE, LEFT)
    text(sl, 0.62, 4.62, 5.90, 0.70,
         [("Response: yearly mean log-weeks-on-chart — seven yearly means (2018–2024); "
           "k = 3 breakpoints → four segments.", 10.5, False, GREY)], spacing=1.15)
    rect(sl, 6.82, 1.66, 5.89, 2.90, BG_CARD, round_=True)
    rect(sl, 6.82, 1.66, 5.89, 0.07, PURPLE)
    text(sl, 7.12, 1.88, 5.30, 2.55,
         [[("How we find them — R/05_changepoint.R", 13, True, DARK)],
          [("Stage 1 — BIC piecewise-linear fit.  ", 10.5, True, DARK),
           ("For each k ∈ {0…4}, fit a k-breakpoint piecewise-linear regression of yearly "
            "mean log-weeks-on-chart against year; BIC = n·log(RSS/n) + (k+3)·log(n) "
            "selects k = 3.", 10.5, False, GREY)],
          [("Stage 2 — Permutation test.  ", 10.5, True, DARK),
           ("Shuffle the yearly means 1,000×, refit k ∈ {0,1,2}, record each shuffle's "
            "minimum BIC; p = share of shuffled min-BIC ≤ observed. p < 0.001 → three "
            "changepoints are not noise.", 10.5, False, GREY)]], spacing=1.18)
    quote_card(sl, 0.62, 5.50, 12.09, 1.10, GREEN,
               [("Reading the 2020 break:  ", 12.5, True, DARK),
                ("post-lockdown acceleration, not the lockdown itself — COVID-Q1 was a "
                 "14-week industry contraction; the listening surge came in 2020-W27+ "
                 "(R/15_covid_qq_features.R).", 11.5, False, GREY)])


def edit_key_insights(sl):
    set_kicker(sl, "INSIGHTS & LIMITATIONS")
    rows = [
        (1.75, "Three regime shifts — 2019 · 2020 · 2022, all p < 0.001",
         "Changepoints in QQ chart behaviour line up with the Douyin takeover, COVID-19, "
         "and the post-2022 platform split."),
        (3.03, "The 2022 structural flip",
         "Hot ↔ Douyin correlation +0.32 → -0.76; edm grew monotonically (0.27 → 0.41) "
         "while guofeng declined (0.34 → 0.24)."),
        (4.31, "Averages identical, song mixes different",
         "349 of 360 titles chart on one platform only, yet their style distributions "
         "match (centroid 3.9°, inside the noise band; per-song AUC 0.66)."),
        (5.59, "Vibration in place, not one-way drift",
         "Six-year audio drift 4.1° is smaller than a single year's swing; monthly "
         "centroids oscillate 8–23.5° — songs rotate, the mix barely moves."),
    ]
    for y, ti, bo in rows:
        text(sl, 1.70, y + 0.08, 10.85, 0.99,
             [[(ti, 14, True, DARK)], [(bo, 10.5, False, GREY)]], anchor=MID, spacing=1.12)
    text(sl, 0.62, 6.79, 11.30, 0.17,
         [("Also: COVID-Q1 2020 was a 14-week industry contraction, not listener-driven "
           "(surge came W27+); LOF vs Euclidean outliers overlap ~0% — complementary "
           "signals.", 9.5, False, GREY)])


# =====================================================================
# part C - new pages
# =====================================================================

def page_why(prs):
    s = add_slide(prs)
    header(s, "PROJECT BACKGROUND", "Why important", GREEN)
    cards = [
        (1.70, GREEN, "01", "The world's largest music market — barely quantified",
         "Chinese streaming is the world's largest recorded-music market, yet "
         "year-over-year listener-behaviour drift is rarely measured at chart-history "
         "level. Seven years of weekly toplists make it measurable."),
        (3.27, CYAN, "02", "Three events should leave fingerprints",
         "2019: Douyin reaches ~400M DAU.  2020: COVID-19 nationwide stay-at-home.  "
         "2022: post-COVID platform / genre ecosystem split. If behaviour really "
         "shifted, the charts should show it."),
        (4.84, PURPLE, "03", "From ranks to sound",
         "Ranks say what was picked; embeddings say what it sounds like. Adding the "
         "audio lens is the step beyond metadata-only chart studies."),
    ]
    for y, ac, num, ti, bo in cards:
        numbered_card(s, 0.62, y, 12.09, 1.42, num, ac, ti, bo, 14, 10.5)
    text(s, 0.62, 6.45, 12.09, 0.35,
         [("If listener behaviour really changed, we should see it twice — in what gets "
           "charted, and in how it sounds.", 11, False, GREY)])
    footer(s)
    return s


def page_works(prs):
    s = add_slide(prs)
    header(s, "PROJECT BACKGROUND", "Existing works & our position", GREEN)
    cards = [
        (1.70, BLUE, "01", "Western chart evolution",
         "Serrà et al. 2012 (Scientific Reports) and Mauch et al. 2015 (Royal Society "
         "Open Science) traced Western popular music through audio features — pitch, "
         "timbre, loudness."),
        (3.27, ORANGE, "02", "Chinese music studies",
         "Focus on metadata, lyrics and recommendation systems; quantitative "
         "chart-history work on Chinese platforms is scarce — no drift studies at this "
         "scale."),
        (4.84, GREEN, "03", "Our position",
         "Bring the Western chart-evolution lens to Chinese charts: 7-year QQ chart "
         "metadata + CLAP audio embeddings of 374 charted songs — one pipeline, both "
         "lenses."),
    ]
    for y, ac, num, ti, bo in cards:
        numbered_card(s, 0.62, y, 12.09, 1.42, num, ac, ti, bo, 14, 10.5)
    text(s, 0.62, 6.45, 12.09, 0.35,
         [("The audio-embedding extension was explicitly listed as future work in the "
           "first draft of this project — this presentation delivers it.", 11, False, GREY)])
    footer(s)
    return s


def page_difficulties(prs):
    s = add_slide(prs)
    header(s, "METHOD AND PIPELINE", "Difficulties — and how we handled them", CYAN)
    cards = [
        (1.70, CORAL, "01", "QQ's public API clamps the window",
         "Periods outside 2018W30–2024W52 are rejected → we work within the window and "
         "document the gap."),
        (2.99, ORANGE, "02", "Play-counts require login",
         "Per-song play counts return code 500003 without login → analysis uses "
         "chart-rank metadata only."),
        (4.28, BLUE, "03", "No public weekly history elsewhere",
         "NetEase, Spotify Charts, Apple Music, Kugou, Douyin, Bilibili, Last.fm all "
         "lack historical endpoints → current-snapshot structural metrics only."),
        (5.57, PURPLE, "04", "Audio coverage is partial",
         "No legal bulk-audio API → MP3s manually downloaded and post-processed: QQ "
         "58.8% coverage, NetEase annual only, QQ 2024 H2 missing → reported as "
         "boundary, not interpreted."),
    ]
    for y, ac, num, ti, bo in cards:
        numbered_card(s, 0.62, y, 12.09, 1.15, num, ac, ti, bo, 13, 10.5)
    footer(s)
    return s


def page_offset(prs):
    s = add_slide(prs)
    header(s, "DATA ANALYSIS", "Yearly offset from the 2018–19 baseline (Q1)", PURPLE)
    cols = [2.0] + [0.82] * 7
    tbl = make_table(s, 0.62, 1.72, cols, [0.42] + [0.72] * 3)
    years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024"]
    set_cell(tbl.cell(0, 0), ("Toplist", 11, True, WHITE), DARK, LEFT)
    for j, yr in enumerate(years, 1):
        set_cell(tbl.cell(0, j), (yr, 11, True, WHITE), DARK)
    data = [
        ("Online Songs", [-2, 2, 22, 6, 24, 34, 65]),
        ("Mainland", [5, -5, 10, -1, 6, 8, -1]),
        ("Hot Songs", [-5, 5, 7, 19, -26, None, None]),
    ]
    for r, (name, vals) in enumerate(data, 1):
        set_cell(tbl.cell(r, 0), (name, 11, True, DARK), BG_CARD, LEFT)
        for j, v in enumerate(vals, 1):
            if v is None:
                set_cell(tbl.cell(r, j), ("–", 10.5, False, GREY), WHITE)
                continue
            if v > 0:
                t = min(abs(v) / 65, 1) * 0.80
                fill = blend(WHITE, GREEN, t)
            elif v < 0:
                t = min(abs(v) / 65, 1) * 0.80
                fill = blend(WHITE, RED, t)
            else:
                t, fill = 0.0, BG_CARD
            txt_c = WHITE if t > 0.5 else DARK
            sign = "+" if v > 0 else ""
            set_cell(tbl.cell(r, j), (f"{sign}{v}", 10.5, True, txt_c), fill)
    text(s, 0.62, 4.42, 7.74, 0.30,
         [("offset in percentage points vs the 2018–19 baseline (%)", 10, False, GREY)])
    rect(s, 8.66, 1.72, 4.05, 3.42, BG_CARD, round_=True)
    rect(s, 8.66, 1.72, 4.05, 0.07, PURPLE)
    text(s, 8.90, 1.95, 3.60, 3.05,
         [[("Highlights", 13.5, True, DARK)],
          [("•  Hot Songs 2022 = -26.3% — fewest songs broke into the top-10: hits "
            "rotated, fewer reached the front (the platform-split year).", 10.5, False, GREY)],
          [("•  Online Songs 2024 = +64.9% — most top-10 reach in six years: the "
            "network / Douyin-crossover era.", 10.5, False, GREY)],
          [("•  Mainland stays within ±10% — the chart front barely moves.",
            10.5, False, GREY)]], spacing=1.2)
    text(s, 0.62, 5.35, 12.09, 1.40,
         [[("How to read it — ", 11.5, True, DARK),
           ("offset = per-year, per-toplist share of songs whose peak rank reaches the "
            "top-10, vs the 2018–19 baseline (R/16_yearly_offset.R). Positive = more "
            "songs break into the top-10 (rising hits); negative = fewer (rotating hits).",
           11.5, False, GREY)],
          [("Changepoints say when the regime shifted; this heatmap says how big the "
            "shift was, per chart, per year. One sparse toplist (baseline coverage only "
            "in 2018) is omitted; Hot Songs 2023–24 are not shown in the source analysis.",
            10.5, False, GREY)]], spacing=1.2)
    footer(s)
    return s


def page_correlation(prs):
    s = add_slide(prs)
    header(s, "DATA ANALYSIS", "Cross-chart correlation — the 2022 flip", PURPLE)
    heads = ["", "Hot Songs", "Online", "Mainland", "EDM", "Rap", "Guofeng", "Douyin"]
    tbl = make_table(s, 0.62, 1.72, [1.55] + [0.95] * 7, [0.50, 0.62, 0.62, 0.62])
    for j, htxt in enumerate(heads):
        if htxt:
            set_cell(tbl.cell(0, j), (htxt, 10.5, True, WHITE), DARK)
        else:
            set_cell(tbl.cell(0, j), ("", 10.5, False, WHITE), DARK)
    rows = [
        ("Hot Songs", [1.00, 0.92, 0.84, -0.66, -0.89, 0.72, -0.76]),
        ("Online", [0.92, 1.00, 0.93, -0.84, 0.00, 0.72, 0.00]),
        ("Douyin", [-0.76, 0.00, 0.16, -0.20, -0.76, 0.12, 1.00]),
    ]
    bold_cells = {(0, 4), (0, 6)}  # (row_idx_in_rows, col_idx_in_vals) -> Hot/Rap, Hot/Douyin
    for r, (name, vals) in enumerate(rows):
        set_cell(tbl.cell(r + 1, 0), (name, 10.5, True, DARK), BG_CARD, LEFT)
        for j, v in enumerate(vals):
            if v > 0:
                t = min(abs(v), 1) * 0.72
                fill = blend(WHITE, GREEN, t)
            elif v < 0:
                t = min(abs(v), 1) * 0.72
                fill = blend(WHITE, RED, t)
            else:
                t, fill = 0.0, BG_CARD
            txt_c = WHITE if t > 0.45 else (GREY if v == 0 else DARK)
            bold = (r, j) in bold_cells
            set_cell(tbl.cell(r + 1, j + 1),
                     (f"{v:.2f}", 10.5, bold, txt_c), fill)
    rect(s, 9.02, 1.72, 3.69, 2.36, BG_CARD, round_=True)
    rect(s, 9.02, 1.72, 3.69, 0.07, PURPLE)
    text(s, 9.26, 1.94, 3.30, 2.00,
         [[("What flips", 13.5, True, DARK)],
          [("•  Hot ↔ Douyin: +0.32 → -0.76 after the 2022 split.", 10.5, False, GREY)],
          [("•  Hot ↔ Rap -0.89 — opposite rotation cycles.", 10.5, False, GREY)],
          [("•  Online ↔ EDM -0.84 — opposite regimes.", 10.5, False, GREY)]], spacing=1.2)
    quote_card(s, 0.62, 4.42, 12.09, 0.90, GREEN,
               [("The 2022 fingerprint:  ", 12.5, True, DARK),
                ("the Hot ↔ Douyin correlation flipped from +0.32 to -0.76 — Douyin hits "
                 "stopped feeding the Hot Songs chart.", 11.5, False, GREY)])
    text(s, 0.62, 5.60, 12.09, 1.10,
         [("Correlation of yearly mean log-weeks-on-chart across QQ's seven toplists "
           "(R/07–08). Positive = two charts age songs in step; negative = one chart's "
           "staples are the other's fresh rotation. Green = positive, red = negative.",
           10.5, False, GREY)], spacing=1.2)
    footer(s)
    return s


def page_genre(prs):
    s = add_slide(prs)
    header(s, "DATA ANALYSIS", "Genre drift — edm up, guofeng down", PURPLE)
    pic(s, ASSETS / "fig_genre_drift.png", 0.62, 1.70, 7.45)
    rect(s, 8.32, 1.70, 4.39, 4.18, BG_CARD, round_=True)
    rect(s, 8.32, 1.70, 4.39, 0.07, PURPLE)
    text(s, 8.56, 1.92, 3.95, 3.75,
         [[("What moved", 13.5, True, DARK)],
          [("•  edm: the only genre that grew monotonically — 27% → 41% of tagged "
            "entries (2020 → 2024).", 10.5, False, GREY)],
          [("•  guofeng: declined 34% → 24%; its dedicated QQ chart launched in 2022.",
            10.5, False, GREY)],
          [("•  rap: peaked at 43% in 2023, fell back to 36% in 2024.",
            10.5, False, GREY)],
          [("Genre membership comes from official chart tags; the three genres "
            "partition the tagged subset.", 10, False, GREY)]], spacing=1.25)
    text(s, 0.62, 6.10, 12.09, 0.55,
         [("Share of genre-tagged chart entries per year (rap + edm + guofeng ≈ 100%). "
           "Source: R/09_genre_drift.R — figure redrawn from the deck's table values in "
           "the deck palette.", 10.5, False, GREY)])
    footer(s)
    return s


def page_crossregion(prs):
    s = add_slide(prs)
    header(s, "DATA ANALYSIS", "Cross-region (Q2) — platform-conditional, not market-wide",
           PURPLE)
    pic(s, IMG / "s23_shape1_0ee7e025_onwhite.png", 0.62, 1.72, 5.85)
    pic(s, IMG / "s23_shape3_1e8c372a_onwhite.png", 6.85, 1.72, 5.85)
    text(s, 0.62, 5.02, 5.85, 0.28,
         [("Share of top-N released ≤ 2018 (higher = older catalogue)", 10.5, False, GREY)],
         align=CENTER)
    text(s, 6.85, 5.02, 5.85, 0.28,
         [("Top-3 artists' share of top-N (higher = star concentration)", 10.5, False, GREY)],
         align=CENTER)
    text(s, 0.62, 5.50, 12.09, 0.60,
         [[("share_old (≤2018):  ", 11, True, DARK),
           ("QQ 18.9%  ·  NetEase 50.6%  ·  Apple CN 84.0%  ·  Apple US 20.0%", 11, False, GREY)],
          [("top-3 artist share:  ", 11, True, DARK),
           ("QQ 24.5%  ·  NetEase 9.1%  ·  Apple CN 54.0%  ·  Apple US 38.0%   ·   artist "
            "Gini ≈ 0.32 on all four platforms", 11, False, GREY)]], spacing=1.3)
    quote_card(s, 0.62, 6.20, 12.09, 0.66, GREEN,
               [("Key insight:  ", 11, True, DARK),
                ("'old catalogue' + 'star concentration' are MORE extreme on Apple Music "
                 "CN than on QQ — QQ's patterns are platform-conditional, not the "
                 "Chinese-market pattern. Apple CN's top-3 = Jay Chou alone; NetEase's = "
                 "many artists at 1–5 songs each.", 10.5, False, GREY)])
    footer(s)
    return s


def page_conclusion(prs):
    s = add_slide(prs)
    header(s, "CONCLUSION", "Three questions, three answers", GREEN)
    cards = [
        (0.62, 1.66, GREEN, "Q1", "Regime shifts — yes",
         "2019, 2020, 2022 are statistically significant regime shifts in QQ chart "
         "behaviour (BIC k = 3, permutation p < 0.001). Hot ↔ Douyin correlation "
         "flipped from +0.32 to strongly negative after 2022."),
        (6.76, 1.66, CYAN, "Q2", "Platform-conditional, not market-wide — yes",
         "The four platforms differ structurally in catalogue freshness and star "
         "concentration. QQ is the balanced Chinese platform; Apple Music CN is the "
         "most old-catalogue and star-driven."),
        (0.62, 3.66, CORAL, "Q3", "The sound — stable",
         f"Average style is indistinguishable across platforms (3.9°, inside the noise "
         f"band) and years (2018→2023 drift 4.1° < one year's swing). What changes is "
         f"which songs chart — separable per song (AUC {AUC_PT:.2f})."),
        (6.76, 3.66, PURPLE, "M", "One pipeline, two lenses",
         "Python fetch + R analysis + CLAP embeddings, reproducible end-to-end. Swap in "
         "new charts or audio and every figure regenerates."),
    ]
    for x, y, ac, num, ti, bo in cards:
        numbered_card(s, x, y, 5.95, 1.85, num, ac, ti, bo, 13.5, 10.5)
    rect(s, 0.62, 5.70, 12.09, 1.10, DARK)
    text(s, 0.92, 5.70, 11.50, 1.10,
         [[("FUTURE WORKS", 10.5, True, GREEN)],
          [("①  weekly cross-platform history, once any public source exposes it     "
            "②  per-song play counts (login-gated)     ③  larger licence-clean audio "
            "corpus + richer encoders (MERT / Jukebox)", 11.5, False, GREY_L)],
          [("Audio embeddings (CLAP) were listed as future work in the metadata-only "
            "draft — delivered in this presentation.", 10.5, False, GREY)]],
         anchor=MID, spacing=1.2)
    footer(s)
    return s


def page_references(prs):
    s = add_slide(prs)
    header(s, "CONCLUSION", "References", GREEN)
    refs = [
        ("Serrà, J. et al. (2012).  ",
         "Measuring the evolution of contemporary western popular music. Scientific Reports."),
        ("Mauch, M. et al. (2015).  ",
         "The evolution of popular music: USA 1960–2010. Royal Society Open Science."),
        ("Li, Y. et al. (2023).  ",
         "MERT: acoustic music understanding model with large-scale self-supervised "
         "training. IJCAI.  (cited for context)"),
        ("Elizalde, B. et al. (2023).  ",
         "CLAP: learning audio concepts from natural language supervision. ICASSP.  — "
         "source of all 512-d audio embeddings"),
        ("Wu, Y. et al. (2022).  ",
         "HTS-AT: a hierarchical token-semantic audio transformer. ICASSP.  — CLAP's "
         "audio encoder"),
        ("Data & code.  ",
         "QQ / NetEase / Apple public endpoints  ·  R 4.2.3 + renv (69 packages)  ·  "
         "pandoc 3.1.13  ·  taste-map figures from r_project/ (R) + matplotlib."),
    ]
    paras = [[(a, 12.5, True, DARK), (t, 12.5, False, GREY)] for a, t in refs]
    text(s, 0.62, 1.70, 12.09, 4.10, paras, spacing=1.35)
    rect(s, 0.62, 6.05, 12.09, 0.70, BG_CARD, round_=True)
    text(s, 0.62, 6.05, 12.09, 0.70,
         [("Jiang Chuyang (3036589703)  ·  Liu Yibo (3036589636)    —    HKU COMP2501 · "
           "Section 1SH · October 2026", 12, True, DARK)], align=CENTER, anchor=MID)
    footer(s)
    return s


# =====================================================================
# part D - assemble
# =====================================================================

def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    make_genre_fig(ASSETS / "fig_genre_drift.png")
    print("figure: fig_genre_drift.png")

    prs = Presentation(str(SRC))
    S = list(prs.slides)
    assert len(S) == 28, f"expected 28 slides, got {len(S)}"
    T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14, T15, T16 = S[:16]
    O17, O18, O19, O20, O21, O22, O23, O24, O25, O26, O27, O28 = S[16:]

    # ---- template edits ----
    edit_title(T1)
    edit_agenda(T2)
    edit_story(T4)
    edit_questions(T5)
    edit_part_section(T6, "From chart scrapes to CLAP audio vectors")
    edit_data_available(T7)
    edit_pipeline(T8)
    edit_part_section(T9, "Changepoints, correlations, genre drift — and the taste map")
    edit_changepoints(T10)
    edit_part_section(T14, "Three answers, future works, references")
    edit_key_insights(T12)

    # ---- our pages: kickers + accent colours ----
    for sl, kicker in [
        (O18, "METHOD AND PIPELINE"), (O19, "METHOD AND PIPELINE"),
        (O20, "METHOD AND PIPELINE"), (O21, "METHOD AND PIPELINE"),
        (O22, "METHOD AND PIPELINE"), (O23, "DATA ANALYSIS"),
        (O24, "DATA ANALYSIS"), (O25, "DATA ANALYSIS"),
        (O26, "DATA ANALYSIS"), (O27, "INSIGHTS & LIMITATIONS"),
    ]:
        set_kicker(sl, kicker, sp=1.0)
    set_accent(O18, CYAN)                      # part 2 colour
    for sl in (O23, O24, O25, O26):            # part 3 colour
        set_accent(sl, PURPLE)
    set_accent(O27, CORAL)                     # part 4 colour

    # ---- O18 card 02: MP3 manual-download note ----
    card = find(O18, 1.70, 3.09)
    rewrite(card, [[("Matched to local audio — manually collected", 14, True, DARK)],
                   [("Normalized-title matching against local MP3s, manually downloaded "
                     "and post-processed (decrypted / converted to standard MP3): QQ 429 "
                     "entries / 319 songs (58.8%), NetEase 60 / 55 (95.2%)",
                     10.5, False, GREY)]], spacing=1.12)

    # ---- new pages ----
    N1 = page_why(prs)
    N2 = page_works(prs)
    N3 = page_difficulties(prs)
    N4 = page_offset(prs)
    N5 = page_correlation(prs)
    N6 = page_genre(prs)
    N7 = page_crossregion(prs)
    N8 = page_conclusion(prs)
    N9 = page_references(prs)

    # ---- delete + reorder + renumber ----
    for sl in (T13, T15, O17, O28):
        delete_slide(prs, sl)
    order = [T1, T2, T3, T4, T5, N1, N2, T6, T7, T8, N3,
             O18, O19, O20, O21, O22,
             T9, T10, N4, N5, N6, N7,
             O23, O24, O25, O26,
             T11, T12, O27, T14, N8, N9, T16]
    reorder(prs, order)
    renumber(order)
    prs.save(str(OUT))

    print(f"saved {OUT}  ({len(order)} pages)")
    for i, sl in enumerate(order, 1):
        first = ""
        for sh in sl.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                first = sh.text_frame.text.strip().split("\n")[0][:60]
                break
        print(f"  {i:2d}. {first}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
