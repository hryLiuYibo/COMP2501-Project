# -*- coding: utf-8 -*-
"""品味变迁地图 + 平台对比图。

关键设计决定：**用 PCA 而不是 t-SNE/UMAP**。
  - PCA 是线性的、全局保距的，年与年之间的「距离」有可比性；
  - t-SNE/UMAP 会为了局部邻居结构牺牲全局几何，年际漂移会失真。
  - CLAP 向量有窄锥效应（全挤在 0.83+ 的余弦区），直接投影到前两轴会显得
    "所有年份都叠在一起"。这不是 bug，是真实几何 —— 我们不掩盖它，
    而是加一张「放大版」子图：只画质心轨迹，轴范围按质心坐标缩放。
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec, patheffects

ROOT = Path(__file__).resolve().parent.parent          # 仓库根
FIG = ROOT / "figures"; FIG.mkdir(exist_ok=True)
INTERIM = ROOT / "data" / "interim"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

GREEN = "#1DB954"
DARK = "#10131A"
GREY = "#6B7280"
BLUE = "#2563EB"
ORANGE = "#F59E0B"
RED = "#DC2626"
PURPLE = "#7C3AED"
BG = "#FFFFFF"

z = np.load(INTERIM / "vectors.npz", allow_pickle=False)
E = z["emb"]
FILES = [str(x) for x in z["files"]]
META = [json.loads(x) for x in z["meta"]]

recs = list(csv.DictReader(open(INTERIM / "vector_index.csv", encoding="utf-8-sig")))
for r in recs:
    r["vec_idx"] = int(r["vec_idx"]); r["year"] = int(r["year"])
main = [r for r in recs if not (r.get("genre") or "").strip()]
anchors = [r for r in recs if (r.get("genre") or "").strip()]


def l2(x):
    n = np.linalg.norm(x, axis=-1, keepdims=True); n[n == 0] = 1
    return x / n


def cen(idx):
    return l2(E[sorted(set(idx))].astype(np.float64).mean(axis=0))


# --------------------------------------------------------------------------- PCA 空间
mu = E.astype(np.float64).mean(axis=0)
U, S, Vt = np.linalg.svd(E.astype(np.float64) - mu, full_matrices=False)
P2 = (E - mu) @ Vt[:2].T          # 所有歌在前两主成分上的坐标
var2 = (S[:2] ** 2) / (S ** 2).sum()

CQ, CN = "#DC2626", "#2563EB"     # QQ=红  网易云=蓝

# --------------------------------------------------------------------------- 图 A：全景散点
fig = plt.figure(figsize=(13.33, 7.0), dpi=200)
gs = gridspec.GridSpec(1, 2, figure=fig, left=0.05, right=0.985,
                       top=0.86, bottom=0.10, wspace=0.16, width_ratios=[1.15, 1])

ax = fig.add_subplot(gs[0, 0])
qi = sorted({r["vec_idx"] for r in main if r["platform"] == "QQ音乐"})
ni = sorted({r["vec_idx"] for r in main if r["platform"] == "网易云"})
ax.scatter(P2[qi, 0], P2[qi, 1], s=26, c=CQ, alpha=0.42, lw=0,
           label=f"QQ音乐 {len(qi)} 首")
ax.scatter(P2[ni, 0], P2[ni, 1], s=46, c=CN, alpha=0.75, lw=0,
           marker="D", label=f"网易云 {len(ni)} 首")
# 全局质心
gall = cen(list(range(len(E))))
pg = (gall - mu) @ Vt[:2].T
ax.scatter([pg[0]], [pg[1]], s=210, marker="*", c=DARK, zorder=5,
           label="全库质心")
ax.set_xlabel(f"主成分 1（{var2[0]*100:.1f}% 方差）", fontsize=11, color=GREY)
ax.set_ylabel(f"主成分 2（{var2[1]*100:.1f}% 方差）", fontsize=11, color=GREY)
ax.set_title("全部上榜歌曲在 512 维向量空间的前两主成分投影", fontsize=12.5,
             color=DARK, fontweight="bold", pad=10)
ax.legend(frameon=False, fontsize=10, loc="upper left")
ax.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#D1D5DB")

# 右：同名歌在两个平台的上榜重合
axr = fig.add_subplot(gs[0, 1])
overlap = defaultdict(lambda: [0, 0])
for r in main:
    if r["platform"] == "QQ音乐":
        overlap[r["title"]][0] += 1
    else:
        overlap[r["title"]][1] += 1
both = {k: v for k, v in overlap.items() if v[0] > 0 and v[1] > 0}
only_q = sum(1 for v in overlap.values() if v[0] > 0 and v[1] == 0)
only_n = sum(1 for v in overlap.values() if v[0] == 0 and v[1] > 0)
axr.barh([2, 1, 0],
         [len(both), only_q, only_n],
         color=[GREEN, CQ, CN], alpha=0.85)
axr.set_yticks([2, 1, 0])
axr.set_yticklabels([f"两平台都上榜\n({len(both)} 首)",
                     f"仅 QQ 上榜\n({only_q} 首)",
                     f"仅网易云上榜\n({only_n} 首)"], fontsize=10)
axr.set_xlabel("唯一歌曲数", fontsize=11, color=GREY)
axr.set_title(f"同一首歌在两个平台的上榜情况\n（重合率 {len(both)/len(overlap)*100:.0f}%，"
              f"两平台合计 {len(overlap)} 首唯一歌）", fontsize=12, color=DARK,
              fontweight="bold", pad=10)
axr.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    axr.spines[s].set_visible(False)
for s in ("left", "bottom"):
    axr.spines[s].set_color("#D1D5DB")
for y, v in zip([2, 1, 0], [len(both), only_q, only_n]):
    axr.text(v + 4, y, str(v), va="center", fontsize=10.5, color=DARK, fontweight="bold")

fig.suptitle("听歌品味变迁地图 · 总览：两个平台的歌几乎共享同一片区域",
             fontsize=15, color=DARK, fontweight="bold", y=0.965)
fig.savefig(FIG / "map_overview.png", facecolor=BG)
plt.close(fig)

# --------------------------------------------------------------------------- 图 B：年度质心轨迹
fig = plt.figure(figsize=(13.33, 6.4), dpi=200)
gs = gridspec.GridSpec(1, 2, figure=fig, left=0.055, right=0.985,
                       top=0.84, bottom=0.115, wspace=0.20)

axa = fig.add_subplot(gs[0, 0])
# 只画质心：轴范围按质心缩放（放大窄锥内部）
for pf, col, mk in (("QQ音乐", CQ, "o"), ("网易云", CN, "D")):
    sub = [r for r in main if r["platform"] == pf]
    yb = defaultdict(list)
    for r in sub:
        yb[r["year"]].append(r["vec_idx"])
    yrs = sorted(yb)
    pts = np.array([(cen(sorted(set(yb[y]))) - mu) @ Vt[:2].T for y in yrs])
    ns = [len(set(yb[y])) for y in yrs]
    axa.plot(pts[:, 0], pts[:, 1], "-", color=col, lw=1.7, alpha=0.65, zorder=2)
    for (x, y), yr, n in zip(pts, yrs, ns):
        big = 22 if n >= 8 else 11
        axa.scatter([x], [y], s=big * 9, c=col, alpha=0.88 if n >= 8 else 0.45,
                    marker=mk, zorder=3, edgecolors="white", lw=1.1)
        axa.annotate(str(yr), (x, y), textcoords="offset points",
                     xytext=(0, 12 if pf == "QQ音乐" else -17),
                     ha="center", fontsize=9.3 if n >= 8 else 7.8,
                     color=col, fontweight="bold" if n >= 8 else "normal")
axa.set_xlabel(f"主成分 1（{var2[0]*100:.1f}%）", fontsize=10.5, color=GREY)
axa.set_ylabel(f"主成分 2（{var2[1]*100:.1f}%）", fontsize=10.5, color=GREY)
axa.set_title("年度质心轨迹（点大小 ∝ 该年歌曲数；空心=样本不足）",
              fontsize=12, color=DARK, fontweight="bold", pad=10)
axa.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    axa.spines[s].set_visible(False)
for s in ("left", "bottom"):
    axa.spines[s].set_color("#D1D5DB")

axb = fig.add_subplot(gs[0, 1])
# 相邻年度漂移角 + bootstrap 不确定度（把噪声带画出来，诚实展示"漂移≈噪声"）
drift_q = [("2018→19", 3.82, 3.23, 33), ("2019→20", 2.99, 1.95, 68),
           ("2020→21", 2.94, 2.33, 53), ("2021→22", 4.62, 2.42, 55),
           ("2022→23", 4.36, 2.17, 58), ("2023→24", 10.59, 8.14, 3)]
drift_n = [("2018→19", 21.56, None, 2), ("2019→20", 15.17, None, 2),
           ("2020→21", 7.21, None, 10), ("2021→22", 9.71, None, 10),
           ("2022→23", 8.51, None, 10), ("2023→24", 9.76, None, 10)]
xs = np.arange(6)
bq = axb.bar(xs - 0.19, [d[1] for d in drift_q], 0.36, color=CQ, alpha=0.85,
             label="QQ音乐（月榜，n=33~68）")
bn = axb.bar(xs + 0.19, [d[1] for d in drift_n], 0.36, color=CN, alpha=0.85,
             label="网易云（年度榜，n=2~11）")
# QQ 的 bootstrap 不确定度（95 分位）
err = [d[2] for d in drift_q]
axb.errorbar(xs - 0.19, [d[1] for d in drift_q], yerr=err, fmt="none",
             ecolor=DARK, elinewidth=1.2, capsize=3.5, alpha=0.75,
             label="QQ音乐质心的 bootstrap 95 分位（噪声水平）")
axb.set_xticks(xs); axb.set_xticklabels([d[0] for d in drift_q], fontsize=9.5)
axb.set_ylabel("相邻年度质心夹角（度）", fontsize=11, color=GREY)
axb.set_title("逐年漂移量 vs 噪声水平：大部分漂移不超过噪声带",
              fontsize=12, color=DARK, fontweight="bold", pad=10)
axb.legend(frameon=False, fontsize=9.3)
axb.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    axb.spines[s].set_visible(False)
for s in ("left", "bottom"):
    axa.spines[s].set_color("#D1D5DB")
    axb.spines[s].set_color("#D1D5DB")
# 2024 样本塌缩警示
axb.annotate("2024 仅 3 首唯一歌\n样本塌缩，不可解读",
             xy=(5 - 0.19, 10.59), xytext=(3.15, 16.2),
             fontsize=9.5, color=RED, fontweight="bold",
             arrowprops=dict(arrowstyle="->", color=RED, lw=1.4))

fig.suptitle("品味变迁：年度质心在原地震动，没有单向漂移", fontsize=15,
             color=DARK, fontweight="bold", y=0.955)
fig.savefig(FIG / "map_trajectory.png", facecolor=BG)
plt.close(fig)

# --------------------------------------------------------------------------- 图 C：月度波动 vs 年度漂移
fig = plt.figure(figsize=(13.33, 4.6), dpi=200)
ax = fig.add_axes([0.06, 0.16, 0.90, 0.70])
mb = defaultdict(list)
for r in main:
    if r["platform"] == "QQ音乐":
        mb[r["period"]].append(r["vec_idx"])
ps = sorted(mb)
first = cen(sorted(set(mb[ps[0]])))
angs = [np.degrees(np.arccos(np.clip(np.dot(first, cen(sorted(set(mb[p])))), -1, 1))) for p in ps]
ax.plot(range(len(ps)), angs, "-o", ms=3.4, lw=1.4, color=CQ, alpha=0.85)
# 年边界
seen = set()
for i, p in enumerate(ps):
    y = p[:4]
    if y not in seen:
        seen.add(y)
        ax.axvline(i, color="#D1D5DB", lw=0.9, ls="--", zorder=0)
        ax.text(i, max(angs) * 1.04, y, fontsize=10, color=GREY, ha="left")
# 年度质心（大点）
sub = [r for r in main if r["platform"] == "QQ音乐"]
yb = defaultdict(list)
for r in sub:
    yb[r["year"]].append(r["vec_idx"])
for y in sorted(yb):
    c = cen(sorted(set(yb[y])))
    a = np.degrees(np.arccos(np.clip(np.dot(first, c), -1, 1)))
    ax.scatter([min(i for i, p in enumerate(ps) if p.startswith(str(y)))],
               [a], s=190, marker="*", c=DARK, zorder=5,
               edgecolors="white", lw=0.8)
ax.scatter([], [], s=170, marker="*", c=DARK, label="年度质心（在同一片区域里抖动）")
ax.set_xlabel("QQ 音乐月度热榜期次（2018.8 ~ 2024.12）", fontsize=11, color=GREY)
ax.set_ylabel("与 2018.8 质心的夹角（度）", fontsize=11, color=GREY)
ax.set_title("月度粒度：月与月之间跳动 8~23°，年度漂移（星标）被月内波动完全淹没",
             fontsize=12.5, color=DARK, fontweight="bold", pad=24)
ax.legend(frameon=False, fontsize=10.5, loc="lower right", bbox_to_anchor=(1.0, 0.02))
ax.set_ylim(0, max(angs) * 1.16)
ax.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#D1D5DB")
fig.savefig(FIG / "map_monthly.png", facecolor=BG)
plt.close(fig)

# --------------------------------------------------------------------------- 图 D：平台差异指标
fig = plt.figure(figsize=(13.33, 4.6), dpi=200)
gs = gridspec.GridSpec(1, 2, figure=fig, left=0.055, right=0.985,
                       top=0.74, bottom=0.155, wspace=0.22)

axd = fig.add_subplot(gs[0, 0])
years = ["2020", "2021", "2022", "2023"]
same_year = [9.13, 7.17, 7.90, 8.58]
xs = np.arange(4)
axd.bar(xs, same_year, 0.55, color=[GREEN, GREEN, GREEN, GREEN], alpha=0.88)
axd.axhline(3.93, color=DARK, lw=1.5, ls="--")
axd.text(3.45, 3.93 + 0.25, "全期质心夹角 3.93°", fontsize=9.6, color=DARK, ha="right")
axd.axhspan(1.9, 3.2, color=GREY, alpha=0.18, label="质心 bootstrap 噪声带 (1.9~3.2°)")
for i, v in enumerate(same_year):
    axd.text(i, v + 0.22, f"{v:.1f}°", ha="center", fontsize=10.5,
             color=DARK, fontweight="bold")
axd.set_xticks(xs); axd.set_xticklabels(years, fontsize=10.5)
axd.set_ylabel("年度质心夹角（度）", fontsize=11, color=GREY)
axd.set_title("控制年份后，两平台差异反而更明显（7~9°）\n—— 全期 3.93° 小是因为年份构成不同",
              fontsize=11.5, color=DARK, fontweight="bold", pad=10)
axd.legend(frameon=False, fontsize=9)
axd.set_ylim(0, 12)
axd.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    axd.spines[s].set_visible(False)
for s in ("left", "bottom"):
    axd.spines[s].set_color("#D1D5DB")

axe = fig.add_subplot(gs[0, 1])
# AUC 分布 + bootstrap 区间
rng = np.random.default_rng(1)
qq_all = sorted({r["vec_idx"] for r in main if r["platform"] == "QQ音乐"})
ne_all = sorted({r["vec_idx"] for r in main if r["platform"] == "网易云"})
cqq, cne = cen(qq_all), cen(ne_all)
def _auc(a, b):
    m = E[a] @ cqq - E[a] @ cne
    k = E[b] @ cqq - E[b] @ cne
    return float((m[:, None] > k[None, :]).mean() + 0.5 * (m[:, None] == k[None, :]).mean())
pt = _auc(qq_all, ne_all)
bs = np.array([_auc(list(rng.choice(qq_all, len(qq_all))),
                    list(rng.choice(ne_all, len(ne_all)))) for _ in range(500)])
axe.hist(bs, bins=34, color=GREEN, alpha=0.75)
axe.axvline(pt, color=DARK, lw=2.2, label=f"AUC = {pt:.3f}")
axe.axvline(np.percentile(bs, 2.5), color=GREY, lw=1.4, ls="--")
axe.axvline(np.percentile(bs, 97.5), color=GREY, lw=1.4, ls="--",
            label=f"95%CI [{np.percentile(bs,2.5):.3f}, {np.percentile(bs,97.5):.3f}]")
axe.axvline(0.5, color=RED, lw=1.6, ls=":", label="0.5 = 完全分不开")
axe.set_xlabel("单曲可分性 AUC", fontsize=11, color=GREY)
axe.set_ylabel("bootstrap 重采样次数", fontsize=11, color=GREY)
axe.set_title("单曲层面可以区分平台（AUC 0.66，CI 不跨 0.5）\n但远未到 1.0 —— 差异在曲目组合，不在平均风格",
              fontsize=11.5, color=DARK, fontweight="bold", pad=10)
axe.legend(frameon=False, fontsize=9.3, loc="upper left")
axe.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    axe.spines[s].set_visible(False)
for s in ("left", "bottom"):
    axe.spines[s].set_color("#D1D5DB")

fig.suptitle("平台差异：平均品味几乎重合，但单曲层面可区分", fontsize=15,
             color=DARK, fontweight="bold", y=0.965)
fig.savefig(FIG / "map_platform.png", facecolor=BG)
plt.close(fig)

# --------------------------------------------------------------------------- 图 E：覆盖报告（诚实展示数据边界）
fig = plt.figure(figsize=(13.33, 4.4), dpi=200)
ax = fig.add_axes([0.06, 0.17, 0.90, 0.66])
cov = json.loads((INTERIM / "coverage.json").read_text(encoding="utf-8"))
by_year = cov["by_year"]
qy = {r["year"]: r for r in by_year if r["platform"] == "QQ音乐"}
ny = {r["year"]: r for r in by_year if r["platform"] == "网易云"}
years = sorted({r["year"] for r in by_year})
xq = [qy.get(y, {}).get("hit", 0) for y in years]
xq_tot = [qy.get(y, {}).get("total", 0) for y in years]
xn = [ny.get(y, {}).get("hit", 0) for y in years]
xn_tot = [ny.get(y, {}).get("total", 0) for y in years]
xs = np.arange(len(years))
b1 = ax.bar(xs - 0.2, xq, 0.38, color=CQ, alpha=0.9, label="QQ音乐 命中/在榜")
b2 = ax.bar(xs + 0.2, xn, 0.38, color=CN, alpha=0.9, label="网易云 命中/在榜")
for i in range(len(years)):
    if xq_tot[i]:
        ax.text(xs[i] - 0.2, xq[i] + 1.2, f"{xq[i]}/{xq_tot[i]}", ha="center",
                fontsize=8.8, color=CQ, fontweight="bold")
    if xn_tot[i]:
        ax.text(xs[i] + 0.2, xn[i] + 1.2, f"{xn[i]}/{xn_tot[i]}", ha="center",
                fontsize=8.8, color=CN, fontweight="bold")
ax.set_xticks(xs); ax.set_xticklabels([str(y) for y in years], fontsize=10.5)
ax.set_ylabel("命中条目数", fontsize=11, color=GREY)
ax.set_title("本地音频覆盖率：QQ 2024 下半年缺音频（仅 5/100），网易云 2018/2019 官方只发 2 首",
             fontsize=12.5, color=DARK, fontweight="bold", pad=12)
ax.legend(frameon=False, fontsize=10)
ax.tick_params(colors=GREY, labelsize=9)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#D1D5DB")
fig.savefig(FIG / "map_coverage.png", facecolor=BG)
plt.close(fig)

print("分析图完成：")
for f in sorted(FIG.glob("map_*.png")):
    print("  ", f.name)
