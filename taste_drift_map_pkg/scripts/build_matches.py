# -*- coding: utf-8 -*-
"""榜单 <-> 本地音频 匹配。

输入（均放在仓库根目录下，见 README 的 "Data layout"）：
  data/raw/charts/qq_monthly_top10.csv          QQ 音乐月度热榜 (2018.8~2024.12, 每月 Top10)
  data/raw/charts/netease_annual_2018-2024.csv  网易云年度榜 (总榜/华语榜/分曲风榜)
  data/raw/audio/qq/                            QQ 本地音频（覆盖到多少算多少）
  data/raw/audio/netease/                       网易云本地音频

输出（写回仓库根）：
  data/interim/charts_matched.csv   每条榜单记录 -> 命中的本地文件（含平台/时间/排名/覆盖率标记）
  data/interim/coverage.csv         逐年逐平台覆盖率，供 PPT 用
"""
from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from pathlib import Path

# --------------------------------------------------------------------------- 路径
# 仓库根 = 本文件的上一级目录（scripts/ 的父目录）。所有输入输出都相对它定位，
# 因此换机器、换目录、换用户名都不需要改代码。
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
INTERIM.mkdir(parents=True, exist_ok=True)

QQ_DIR = RAW / "audio" / "qq"
NE_DIR = RAW / "audio" / "netease"
OUT = ROOT

# ----------------------------------------------------------------------------- 归一化
# 榜单歌名与文件名差异很大：全半角、括号版本号、feat.、空格、"、_"分隔符…
# 这里做激进归一化，只保留"字面上真正决定是不是同一首歌"的字符。

_PUNC = re.compile(r"[\s\-_·、,，.。!！?？'\"“”‘’~～:：;；/\\|()\[\]{}（）【】]")
_BRACKET = re.compile(r"[\(\（\[【][^\)\）\]】]*[\)\）\]】]")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str, drop_bracket: bool = True) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKC", s)          # 全角 -> 半角
    s = strip_accents(s)
    if drop_bracket:
        s = _BRACKET.sub("", s)                   # 去掉 (Live) / （吉他版） 等
    s = _PUNC.sub("", s)
    return s


def norm_keep_bracket(s: str) -> str:
    return norm(s, drop_bracket=False)


def split_artist(s: str) -> list[str]:
    """把 'A/B/C' 'A; B' 'A、B' 拆成艺名列表。"""
    parts = re.split(r"[/;；、,，&]|feat\.?|ft\.?", (s or ""), flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def artist_tokens(s: str) -> set[str]:
    toks: set[str] = set()
    for a in split_artist(s):
        n = norm(a)
        if n:
            toks.add(n)
    return toks


# ----------------------------------------------------------------------------- 扫描音频
def scan(d: Path) -> list[Path]:
    files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".mp3", ".flac", ".m4a", ".wav")]
    files.sort(key=lambda p: p.name.lower())
    return files


def index_audio(files: list[Path]) -> list[dict]:
    out = []
    for p in files:
        stem = p.stem
        # 文件名约定： "歌手 - 歌名"（可能含多个歌手，用 ; 或 _ 或 / 分隔）
        if " - " in stem:
            art, _, title = stem.partition(" - ")
        else:
            art, title = "", stem
        out.append({
            "file": p.name,
            "path": str(p),
            "title_raw": title,
            "art_raw": art,
            "t": norm(title),
            "t_keep": norm_keep_bracket(title),
            "a": artist_tokens(art),
        })
    return out


# ----------------------------------------------------------------------------- 匹配
# ---------------------------------------------------------------------------
# 匹配决策（分级，不只看总分）
#
# 实际数据里"同名不同曲"非常密集 —— 中文歌名短、复用率高：
#     《灰姑娘》陈雪凝 vs 郑钧      《奔向你》周深 vs 张睿
#     《星辰大海》群星 vs 黄霄雲     《喜欢你》 TFBOYS vs 希林娜依高
#     《太阳》刘鹏 vs en             《星火》吉克隽逸 vs 张杰
# 只按歌名相似度或总分阈值都拦不住（它们全是 0.80）。所以改成显式分级：
#
#   T1  归一化歌名完全相等 + 歌手有交集        -> 直接采用（最可信）
#   T2  归一化歌名完全相等 + 歌手对不上        -> 采用，但标记 artist_mismatch
#   T3  歌名靠"包含关系"命中（≥0.85）        -> 必须歌手有交集，否则**丢弃**
#
# T3 丢弃的典型误配：《余情未了》魏新雨→周深《余情》、《大风吹倒梧桐树》侯泽润
#                   →王赫野《大风吹》、《忘川彼岸》→《彼岸》、《侠客行》→《侠》
# 收益 >> 代价：丢几条只让年度样本略小，混进错歌会直接污染质心。
# ---------------------------------------------------------------------------
def name_kind(title: str, cand: dict) -> tuple[str, float]:
    """返回 ('exact'|'partial'|'none', 歌名得分)。"""
    ct, ctk = norm(title), norm_keep_bracket(title)
    if not ct:
        return "none", 0.0
    if ct == cand["t"] or (ctk and ctk == cand["t_keep"]):
        return "exact", 1.0
    if len(ct) >= 3 and (ct in cand["t_keep"] or cand["t_keep"] in ct):
        shorter = min(len(ct), len(cand["t_keep"]))
        longer = max(len(ct), len(cand["t_keep"]))
        return "partial", 0.72 + 0.18 * (shorter / max(longer, 1))
    if len(ct) >= 4 and (ct in cand["t"] or cand["t"] in ct):
        shorter = min(len(ct), len(cand["t"]))
        longer = max(len(ct), len(cand["t"]))
        return "partial", 0.66 + 0.16 * (shorter / max(longer, 1))
    s1, s2 = set(ct), set(cand["t_keep"])
    if s1 and s2:
        j = len(s1 & s2) / len(s1 | s2)
        if j >= 0.85:
            return "partial", 0.55 + 0.3 * (j - 0.85) / 0.15
    return "none", 0.0


def artists_overlap(chart_artist: str, cand: dict) -> bool:
    ca = artist_tokens(chart_artist)
    if not ca or not cand["a"]:
        return True                      # 无从判断，不据此否决
    if ca & cand["a"]:
        return True
    for x in ca:
        for y in cand["a"]:
            if len(x) >= 2 and len(y) >= 2 and (x in y or y in x):
                return True
    return False


def best_match(title: str, artist: str, pool: list[dict]):
    """按「歌手是否吻合 → 歌名得分」排序挑最佳候选，再按分级规则决定收不收。

    返回 (候选|None, 歌名得分, 判定说明, 歌手是否吻合)
    """
    best, bs, bk, bov = None, 0.0, "none", False
    for c in pool:
        k, ns = name_kind(title, c)
        if k == "none":
            continue
        ov = artists_overlap(artist, c)
        if best is None or (1 if ov else 0, ns) > (1 if bov else 0, bs):
            best, bs, bk, bov = c, ns, k, ov
    if best is None:
        return None, 0.0, "no_candidate", False

    if bk == "exact":
        return best, bs, "exact" if bov else "exact-noartist", bov
    if bk == "partial" and bov:
        return best, bs, "partial+artist", True
    return None, bs, f"rejected:{bk}{'' if bov else '-artist'}", bov



# ----------------------------------------------------------------------------- 人工裁决表
# 上面分级规则仍然会放进来一批"歌名完全一致但歌手对不上"的条目。逐条核过，结论如下：
#
#   ACCEPT —— 是同一首歌，歌手字段差异有明确原因：
#     大碗宽面    吴亦凡        -> 文件名把"吴亦凡"写成了"吴亦为"（错别字）
#     床          草東沒有派對   -> 同名同曲，榜单用繁体、文件用简体
#     恶人先告状   河北有为青年   -> 同一首歌，艺人被标成了专辑/乐队别名
#     一线之隔    永彬Ryan.B/…  -> 同名，DJ 版；歌手串一致
#     I Love You 3000 II        -> 同一首，榜单带 II、文件不带
#     喜欢你(Live) 希林娜依高     -> 翻唱同一首《喜欢你》→ 见下方 COVER 注释
#     其实都没有   半吨兄弟       -> 与 en 版同曲不同版本
#     太阳(你看着我眼睛) 刘鹏      -> 与 en《太阳》同曲不同版本
#     解药(新版)   来一碗老于     -> 与 Fanfan 版同曲（改名翻唱）
#     星辰大海     群星          -> 与黄霄雲版同曲（多版本）
#     별(星)       Loco         -> 同曲不同艺人标注
#     时光旅途(纯音乐版)          -> 同曲纯音乐版
#
#   REJECT —— 确实不是同一首歌，必须剔除，否则污染质心：
#     灰姑娘   陈雪凝  vs  郑钧《灰姑娘》      两首完全不同的歌
#     奔向你   周深    vs  张睿《奔向你》      两首完全不同的歌
#     星火     吉克隽逸 vs 张杰《星火》        两首完全不同的歌
#     爱，存在  王靖雯  vs  林小珂《爱，存在》   两首完全不同的歌
#     Pull Up  蔡徐坤  vs  Luh Kel《Pull Up》  两首完全不同的歌
#     Scary Movie 严浩翔 vs 严浩翔《Y》        歌名根本不同，被包含关系误配
#
# 键 = (平台, 期次, 排名, 歌名)，值 = True 采用 / False 剔除
MANUAL_DECISIONS: dict[tuple, bool] = {
    ("QQ音乐", "2019-04", 3,  "大碗宽面"): True,
    ("QQ音乐", "2019-05", 4,  "大碗宽面"): True,
    ("QQ音乐", "2018-12", 7,  "별 (星)"): True,
    ("QQ音乐", "2020-05", 10, "喜欢你 (Live)"): True,
    ("QQ音乐", "2021-08", 7,  "解药 (新版)"): True,
    ("QQ音乐", "2021-09", 10, "解药 (新版)"): True,
    ("QQ音乐", "2022-12", 4,  "时光旅途 (纯音乐版)"): True,
    ("QQ音乐", "2023-10", 9,  "太阳 (你看着我眼睛)"): True,
    ("QQ音乐", "2023-11", 10, "其实都没有"): True,
    ("QQ音乐", "2019-11", 10, "星辰大海"): True,
    ("网易云", "2023", 1, "床"): True,
    ("网易云", "2024", 1, "恶人先告状"): True,
    ("QQ音乐", "2021-04", 3,  "一线之隔"): True,
    ("网易云", "2019", 1, "I Love You 3000 II"): True,

    ("QQ音乐", "2019-05", 7,  "灰姑娘"): False,
    ("QQ音乐", "2022-11", 1,  "奔向你"): False,
    ("QQ音乐", "2022-07", 6,  "星火"): False,
    ("QQ音乐", "2020-07", 5,  "爱，存在"): False,
    ("QQ音乐", "2020-07", 6,  "爱，存在"): False,
    ("QQ音乐", "2018-08", 1,  "Pull Up"): False,
    ("QQ音乐", "2024-04", 7,  "Scary Movie"): False,
    ("QQ音乐", "2024-05", 3,  "Scary Movie"): False,
}


def arbitrate(platform: str, period: str, rank: int, title: str, default: bool) -> bool:
    """人工裁决优先，其次是规则结论。"""
    return MANUAL_DECISIONS.get((platform, period, rank, title), default)


# ----------------------------------------------------------------------------- 主流程
def main() -> int:
    qq_files = scan(QQ_DIR)
    ne_files = scan(NE_DIR)
    qq_idx, ne_idx = index_audio(qq_files), index_audio(ne_files)
    print(f"本地音频: QQ={len(qq_idx)}  网易云={len(ne_idx)}")

    rows: list[dict] = []

    # ---- QQ 月榜 ----
    with open(RAW / "charts" / "qq_monthly_top10.csv", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            per = f'{r["年"]}-{int(r["月"]):02d}'
            rk = int(r["排名"])
            m, s, how, _ov = best_match(r["歌名"], r["歌手"], qq_idx)
            if m and not arbitrate("QQ音乐", per, rk, r["歌名"], True):
                m, how = None, "rejected:manual"
            rows.append({
                "platform": "QQ音乐",
                "year": int(r["年"]),
                "month": int(r["月"]),
                "rank": rk,
                "period": per,
                "title": r["歌名"],
                "artist": r["歌手"],
                "matched": 1 if m else 0,
                "file": m["file"] if m else "",
                "path": m["path"] if m else "",
                "score": round(s, 4), "match_how": how,
            })

    # ---- 网易云年度榜 ----
    NE_KEEP = {"年度总榜·单曲", "华语单曲榜", "语种单曲榜（其他语种）", "年度人气单曲（用户投票）"}
    with open(RAW / "charts" / "netease_annual_2018-2024.csv", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            title = (r["歌曲名"] or "").strip()
            if not title or "未公布" in title:
                continue
            if r["榜单类别"] not in NE_KEEP:
                continue      # 分曲风榜的 8 条单独算：它们本身就是"流派标签"，见下
            rank = r["排名"].strip()
            rk = int(rank) if rank.isdigit() else 0
            m, s, how, _ov = best_match(title, r["艺人"], ne_idx)
            if m and not arbitrate("网易云", r["年份"], rk, title, True):
                m, how = None, "rejected:manual"
            rows.append({
                "platform": "网易云",
                "year": int(r["年份"]),
                "month": 0,
                "rank": rk,
                "period": r["年份"],
                "title": title,
                "artist": r["艺人"],
                "matched": 1 if m else 0,
                "file": m["file"] if m else "",
                "path": m["path"] if m else "",
                "score": round(s, 4), "match_how": how,
            })

    # ---- 分曲风榜：作为"流派锚点"，用来给地图上的点做语义注释 ----
    genres: list[dict] = []
    with open(RAW / "charts" / "netease_annual_2018-2024.csv", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["榜单类别"] != "分曲风单曲榜":
                continue
            title = (r["歌曲名"] or "").strip()
            if not title:
                continue
            m, s, how, _ov = best_match(title, r["艺人"], ne_idx)
            genres.append({
                "platform": "网易云",
                "year": int(r["年份"]),
                "month": 0,
                "rank": 0,
                "period": r["年份"],
                "genre": r["语种"],
                "title": title,
                "artist": r["艺人"],
                "matched": 1 if m else 0,
                "file": m["file"] if m else "",
                "path": m["path"] if m else "",
                "score": round(s, 4), "match_how": how,
            })
    out_rows = rows + genres

    # ---- 写表 ----
    cols = ["platform", "year", "month", "rank", "period", "genre", "title", "artist",
            "matched", "score", "match_how", "file", "path"]
    with open(INTERIM / "charts_matched.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    # ---- 覆盖率统计 ----
    cov: dict[tuple, list[int]] = {}
    for r in rows:
        k = (r["platform"], r["year"])
        cov.setdefault(k, [0, 0])
        cov[k][0] += 1
        cov[k][1] += r["matched"]

    print("\n%-8s %-6s %6s %6s %8s" % ("平台", "年份", "总条", "命中", "覆盖率"))
    cov_rows = []
    for (pf, yr), (tot, hit) in sorted(cov.items()):
        print("%-8s %-6d %6d %6d %7.1f%%" % (pf, yr, tot, hit, 100 * hit / tot))
        cov_rows.append({"platform": pf, "year": yr, "total": tot, "hit": hit,
                         "rate": round(100 * hit / tot, 2)})

    # 全期覆盖率
    print("\n全期：")
    summary = {}
    for pf in ("QQ音乐", "网易云"):
        sub = [r for r in rows if r["platform"] == pf]
        tot = len(sub); hit = sum(r["matched"] for r in sub)
        uniq = {r["title"] for r in sub}
        uniq_hit = {r["title"] for r in sub if r["matched"]}
        print("  %s  条数 %d/%d = %.1f%%   唯一歌名 %d/%d = %.1f%%"
              % (pf, hit, tot, 100 * hit / tot, len(uniq_hit), len(uniq), 100 * len(uniq_hit) / len(uniq)))
        summary[pf] = {"rows_total": tot, "rows_hit": hit,
                       "uniq_total": len(uniq), "uniq_hit": len(uniq_hit)}

    (INTERIM / "coverage.json").write_text(json.dumps(
        {"by_year": cov_rows, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n写出:", INTERIM / "charts_matched.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
