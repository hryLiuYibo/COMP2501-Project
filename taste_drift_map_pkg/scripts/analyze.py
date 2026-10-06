# -*- coding: utf-8 -*-
"""品味变迁分析。

回答三个问题：
  Q1 两个平台在听歌品味上有什么差异？
  Q2 每个平台的品味如何随时间变化？
  Q3 （原理部分的数据支撑）一首歌怎么变成向量

全部结论都以 json + csv 落盘，供 PPT 直接引用，避免"图上一个数字、正文另一个数字"。
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent          # 仓库根
INTERIM = ROOT / "data" / "interim"
OUT = INTERIM

# --------------------------------------------------------------------------- 载入
z = np.load(OUT / "vectors.npz", allow_pickle=False)
E = z["emb"]                      # (N,512) 已 L2 归一化
FILES = [str(x) for x in z["files"]]
PATHS = [str(x) for x in z["paths"]]

recs = list(csv.DictReader(open(OUT / "vector_index.csv", encoding="utf-8-sig")))
for r in recs:
    r["vec_idx"] = int(r["vec_idx"])
    r["year"] = int(r["year"])
    r["month"] = int(r["month"])
    r["rank"] = int(r["rank"]) if str(r["rank"]).isdigit() else 0
    if r.get("genre"):
        r["genre"] = r["genre"].strip()

# 语种/曲风榜那 15 条是"流派锚点"，不参与年度质心（它们的入选机制是分曲风，不是总热度）
anchors = [r for r in recs if r.get("genre")]
main = [r for r in recs if not r.get("genre")]
print(f"总记录 {len(recs)}（主榜 {len(main)}，流派锚点 {len(anchors)}），唯一向量 {len(E)}")

RESULT: dict = {}

# --------------------------------------------------------------------------- 工具
def l2(x, axis=-1):
    n = np.linalg.norm(x, axis=axis, keepdims=True)
    n[n == 0] = 1.0
    return x / n


def centroid(idx: list[int]) -> np.ndarray:
    """质心 = 单位向量平均后再归一化。等价于最大平均余弦。"""
    if not idx:
        return np.zeros(E.shape[1], dtype=np.float64)
    return l2(E[idx].astype(np.float64).mean(axis=0))


def cosine(a, b) -> float:
    return float(np.dot(a, b))


def angle_deg(a, b) -> float:
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b), -1, 1))))


# --------------------------------------------------------------------------- Q1 平台差异
def platform_diff() -> dict:
    plat: dict[str, dict] = {}
    for p in ("QQ音乐", "网易云"):
        sub = [r for r in main if r["platform"] == p]
        idx = sorted({r["vec_idx"] for r in sub})
        plat[p] = {"n_records": len(sub), "n_songs": len(idx), "idx": idx}
        # 年份范围
        yrs = sorted({r["year"] for r in sub})
        plat[p]["years"] = [yrs[0], yrs[-1]]
        plat[p]["by_year"] = {}
        for y in yrs:
            yi = sorted({r["vec_idx"] for r in sub if r["year"] == y})
            plat[p]["by_year"][y] = yi

    # -- 质心与夹角 --
    cq = centroid(plat["QQ音乐"]["idx"])
    cn = centroid(plat["网易云"]["idx"])
    res = {
        "n_qq": plat["QQ音乐"]["n_records"], "n_ne": plat["网易云"]["n_records"],
        "uniq_qq": plat["QQ音乐"]["n_songs"], "uniq_ne": plat["网易云"]["n_songs"],
        "years_qq": plat["QQ音乐"]["years"], "years_ne": plat["网易云"]["years"],
        "centroid_cosine": cosine(cq, cn),
        "centroid_angle_deg": angle_deg(cq, cn),
    }

    # -- 可分性 AUC：用"离哪个质心更近"给单一首歌打分 --
    allidx = np.array(plat["QQ音乐"]["idx"] + plat["网易云"]["idx"])
    label = np.array([1] * len(plat["QQ音乐"]["idx"]) + [0] * len(plat["网易云"]["idx"]))
    sq = E[allidx] @ cq
    sn = E[allidx] @ cn
    margin = sq - sn                      # >0 偏向 QQ，<0 偏向网易云
    # AUC = P(随机的 QQ 歌 margin > 随机的网易云歌 margin)
    pos, neg = margin[label == 1], margin[label == 0]
    cmp = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
    res["auc_qq_vs_ne"] = float(cmp)
    res["margin_mean_qq"] = float(pos.mean())
    res["margin_mean_ne"] = float(neg.mean())
    res["margin_std"] = float(margin.std())

    # -- 年度质心之间的交叉比较（逐年对比而非只比全期） --
    cross = []
    for y in sorted(set(res["years_qq"]) | set(res["years_ne"])):
        qi, ni = plat["QQ音乐"]["by_year"].get(y, []), plat["网易云"]["by_year"].get(y, [])
        if len(qi) < 3 or len(ni) < 3:
            continue
        a, b = centroid(qi), centroid(ni)
        cross.append({"year": y, "n_qq": len(qi), "n_ne": len(ni),
                      "cosine": cosine(a, b), "angle_deg": angle_deg(a, b)})
    res["per_year_cross"] = cross

    # -- 库内紧致度：各自内部平均两两余弦（衡量风格集中度） --
    for p, k in (("QQ音乐", "compact_qq"), ("网易云", "compact_ne")):
        ii = plat[p]["idx"]
        M = E[ii] @ E[ii].T
        n = len(ii)
        off = (M.sum() - np.trace(M)) / (n * (n - 1))
        res[k] = float(off)
    return res


RESULT["Q1_platform_diff"] = platform_diff()

# --------------------------------------------------------------------------- Q2 时间变迁
def temporal(pf: str) -> dict:
    sub = [r for r in main if r["platform"] == pf]
    is_qq = pf == "QQ音乐"

    # 期次聚合：QQ 按月，网易云按年（网易云官方只发年度榜，无法按月）
    period_key = (lambda r: f'{r["year"]}-{r["month"]:02d}') if is_qq else (lambda r: str(r["year"]))
    buckets: dict[str, list[int]] = defaultdict(list)
    for r in sub:
        buckets[period_key(r)].append(r["vec_idx"])
    periods = sorted(buckets.keys())
    cents = {p: centroid(sorted(set(buckets[p]))) for p in periods}

    # 相邻期次漂移
    drift = []
    for a, b in zip(periods, periods[1:]):
        drift.append({"from": a, "to": b,
                      "cosine": cosine(cents[a], cents[b]),
                      "angle_deg": angle_deg(cents[a], cents[b])})

    # 相对起点的累计漂移
    base = cents[periods[0]]
    cum = [{"period": p, "cosine_to_first": cosine(base, cents[p]),
            "angle_to_first_deg": angle_deg(base, cents[p]),
            "n": len(set(buckets[p]))} for p in periods]

    # 年度质心（QQ 也可按年再算一次，便于和网易云同轴比较）
    yb: dict[int, list[int]] = defaultdict(list)
    for r in sub:
        yb[r["year"]].append(r["vec_idx"])
    years = sorted(yb.keys())
    ycent = {y: centroid(sorted(set(yb[y]))) for y in years}
    ydrift = [{"from": a, "to": b, "cosine": cosine(ycent[a], ycent[b]),
               "angle_deg": angle_deg(ycent[a], ycent[b]),
               "n_from": len(set(yb[a])), "n_to": len(set(yb[b]))}
              for a, b in zip(years, years[1:])]
    # 全期跨度
    overall = {"first_year": years[0], "last_year": years[-1],
               "cosine": cosine(ycent[years[0]], ycent[years[-1]]),
               "angle_deg": angle_deg(ycent[years[0]], ycent[years[-1]])}

    # 库内离散度随时间（看品味是变宽还是变窄）
    spread = [{"year": y, "n": len(set(yb[y])),
               "mean_pairwise_cosine": float(
                   (lambda M, n: (M.sum() - np.trace(M)) / (n * (n - 1)))(
                       E[sorted(set(yb[y]))] @ E[sorted(set(yb[y]))].T, len(set(yb[y]))))}
              for y in years if len(set(yb[y])) >= 3]

    # 语种/国别构成：用歌名是否含 CJK、艺人名特征粗判
    def is_cjk(s: str) -> bool:
        return any("\u4e00" <= c <= "\u9fff" for c in (s or ""))

    lang = []
    for y in years:
        rs = [r for r in sub if r["year"] == y]
        cn_title = sum(1 for r in rs if is_cjk(r["title"]))
        lang.append({"year": y, "n": len(rs),
                     "chinese_title": cn_title,
                     "chinese_title_pct": round(100 * cn_title / len(rs), 1),
                     "non_chinese_title": len(rs) - cn_title})

    return {"granularity": "month" if is_qq else "year",
            "periods": periods,
            "period_centroids": {p: cents[p].tolist() for p in periods},
            "adjacent_drift": drift, "cumulative": cum,
            "year_centroids": {str(y): ycent[y].tolist() for y in years},
            "year_drift": ydrift, "overall": overall,
            "spread": spread, "language": lang,
            "n_records": len(sub), "n_songs": len({r["vec_idx"] for r in sub})}


RESULT["Q2_temporal"] = {"QQ音乐": temporal("QQ音乐"), "网易云": temporal("网易云")}

# --------------------------------------------------------------------------- 主成分空间（给地图用）
allidx = sorted(range(len(E)))
X = E[allidx].astype(np.float64)
mu = X.mean(axis=0)
Xc = X - mu
U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
var = (S ** 2) / (S ** 2).sum()
RESULT["pca"] = {"explained": [float(v) for v in var[:10]],
                 "axis": Vt[:3].tolist()}

# --------------------------------------------------------------------------- Q3 单曲原理链：挑一首"链条比较好讲"的歌
# 选标准：主榜里排名靠前、有中文名、文件在网易云库（便于同时展示中文检索）
probe_pool = [r for r in main if r["platform"] == "网易云" and r["rank"] == 1]
probe = None
for r in sorted(probe_pool, key=lambda r: r["year"]):
    if r["title"] in ("雪 Distance", "向云端", "笼"):
        probe = r
        break
if probe is None:
    probe = probe_pool[0] if probe_pool else main[0]
RESULT["probe_song"] = {"title": probe["title"], "artist": probe["artist"],
                        "platform": probe["platform"], "period": probe["period"],
                        "rank": probe["rank"], "file": probe["file"],
                        "vec_idx": probe["vec_idx"]}

# --------------------------------------------------------------------------- 落盘
(OUT / "analysis.json").write_text(
    json.dumps(RESULT, ensure_ascii=False, indent=2), encoding="utf-8")

# --------------------------------------------------------------------------- 打印摘要
d = RESULT["Q1_platform_diff"]
print("\n" + "=" * 70)
print("Q1  平台差异")
print(f"  QQ音乐 : {d['n_qq']} 条榜单位置 / {d['uniq_qq']} 首唯一歌 / {d['years_qq']}")
print(f"  网易云 : {d['n_ne']} 条榜单位置 / {d['uniq_ne']} 首唯一歌 / {d['years_ne']}")
print(f"  全期质心夹角 : {d['centroid_angle_deg']:.2f}°   (余弦 {d['centroid_cosine']:.4f})")
print(f"  单曲可分性 AUC: {d['auc_qq_vs_ne']:.3f}   (0.5=完全分不开, 1.0=完全可分)")
print(f"  库内平均两两余弦: QQ {d['compact_qq']:.4f}   网易云 {d['compact_ne']:.4f}")
print("  逐年质心对比:")
for c in d["per_year_cross"]:
    print(f"    {c['year']}  n={c['n_qq']:>3}/{c['n_ne']:<3}  夹角 {c['angle_deg']:6.2f}°  余弦 {c['cosine']:.4f}")

print("\n" + "=" * 70)
print("Q2  品味变迁")
for pf in ("QQ音乐", "网易云"):
    t = RESULT["Q2_temporal"][pf]
    print(f"\n  【{pf}】粒度={t['granularity']}  {t['n_records']} 条 / {t['n_songs']} 首")
    print(f"    首末年度质心夹角: {t['overall']['angle_deg']:.2f}° "
          f"({t['overall']['first_year']} -> {t['overall']['last_year']})")
    print("    逐年漂移:")
    for x in t["year_drift"]:
        print(f"      {x['from']}->{x['to']}  {x['angle_deg']:6.2f}°  (n={x['n_from']}->{x['n_to']})")
    print("    库内离散度(平均两两余弦, 越低越分散):")
    for s in t["spread"]:
        print(f"      {s['year']}  n={s['n']:>3}  {s['mean_pairwise_cosine']:.4f}")
    print("    中文歌名占比:")
    for l in t["language"]:
        print(f"      {l['year']}  {l['chinese_title_pct']:>5.1f}%  ({l['chinese_title']}/{l['n']})")

print("\n" + "=" * 70)
print("PCA 前 5 个主成分方差占比:",
      "  ".join(f"{v*100:.1f}%" for v in RESULT["pca"]["explained"][:5]))
print("原理链样例歌曲:", RESULT["probe_song"])
print("\n写出 analysis.json")
