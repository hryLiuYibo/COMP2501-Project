# -*- coding: utf-8 -*-
"""把分析中间产物导出成扁平 CSV，供 R 端直接 readr::read_csv() 使用。

设计原则
--------
* R 端不应该依赖 Python 的 .npz / .json —— 一律扁平成 CSV。
* 所有 CSV 都是 utf-8-sig（Excel 友好，R 的 read_csv 也能正常吃掉 BOM）。
* 平台名在 CSV 里保留中文原文（数据即事实），**翻译只发生在 R 画图时**：
  R 端用 plot_labels.R 里的字典映射到 "QQ Music" / "NetEase Cloud Music"。
  这样数据层不需要为改语言而重跑。

产出（r_project/data/）
-----------------------
songs.csv         每首歌一行：id / 平台 / 年 / 月 / 榜期 / 排名 / 标题 / 歌手 / 文件名 / match_how
                  这是 R 端的「主表」（tidy 长表，一首歌上榜多次就有多行）
songs_unique.csv  每首唯一歌一行：id / 标题 / 歌手 / 平台集合 / 上榜次数 / 文件名
vectors.csv       386 行 × 512 列的主成分坐标（只给 R 画图用的 PC1..PC10，不是全 512 维）
                  —— 全 512 维对 R 画图无用，且文件巨大；PCA 坐标足够复原所有二维图
centroid_pc.csv   按（平台 × 年）聚合的质心 PC 坐标 + 该年歌曲数 + bootstrap 离散度
monthly_pc.csv    QQ 音乐按月聚合的质心 PC 坐标（画月度波动用）
metrics_q1.csv    平台差异指标（长表：metric / platform / value / lo / hi / note）
drift_annual.csv  年度相邻漂移 + bootstrap 噪声带
coverage.csv      逐年覆盖率（分子分母都在，R 端自己算比例）
pca_var.csv       PCA 各主成分解释方差比
probe_chain.csv   原理链用：《雪 Distance》的 17 个窗口两两余弦矩阵（长表 window_i/window_j/cos）
probe_meta.csv    探针歌元信息（标题/歌手/时长/窗口数/库内平均余弦…）
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent          # 仓库根
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "r_project" / "data"

# clap-audio-vectorizer：优先环境变量，其次仓库同级目录（同 build_vectors.py）
CLAPV = Path(os.environ.get("CLAP_VECTORIZER",
                            ROOT.parent / "clap-audio-vectorizer")).expanduser()
OUT.mkdir(parents=True, exist_ok=True)

PLATFORM_EN = {"QQ音乐": "QQ Music", "网易云": "NetEase Cloud Music"}


def w(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)
    print(f"  {path.name:24s} {len(rows):6d} 行")


def main() -> int:
    z = np.load(INTERIM / "vectors.npz", allow_pickle=True)
    E = z["emb"].astype(np.float64)          # (N, 512)
    files = [str(x) for x in z["files"]]     # 每个向量对应的音频文件名
    keys = [str(x) for x in z["keys"]]

    A = json.load(open(INTERIM / "analysis.json", encoding="utf-8"))
    cov = json.load(open(INTERIM / "coverage.json", encoding="utf-8"))

    # ---------------------------------------------------------------- 匹配表
    with open(INTERIM / "charts_matched.csv", encoding="utf-8-sig") as f:
        matched = list(csv.DictReader(f))
    with open(INTERIM / "vector_index.csv", encoding="utf-8-sig") as f:
        vidx = list(csv.DictReader(f))

    # 与 analyze.py / make_map_figs.py 完全一致的口径：
    # main = 无 genre 标签的行（QQ 月榜 + 网易云总榜/华语榜）；
    # 带 genre 的行是网易云分曲风榜（anchor），只做锚点不进分析
    vidx = [r for r in vidx if not (r.get("genre") or "").strip()]

    # 复用 build_matches 的标题归一化（保证与 deck 的重合统计口径一致）
    import sys
    sys.path.insert(0, str(INTERIM))
    from build_matches import norm  # noqa: E402

    # 先按「归一化标题」统计每个标题出现在哪些平台（deck 口径：标题相同 = 同一首歌）
    title_platforms = defaultdict(set)
    for r in vidx:
        title_platforms[norm(r["title"], drop_bracket=True)].add(r["platform"])

    def overlap_class(platform: str, title: str) -> str:
        tps = title_platforms.get(norm(title, drop_bracket=True), set())
        if len(tps) >= 2:
            return "Both platforms"
        return "QQ Music only" if platform == "QQ音乐" else "NetEase only"

    # vec_idx 是向量在 E 里的行号；vector_index.csv 里已经带好
    rows_songs = []
    for i, r in enumerate(vidx):
        rows_songs.append([
            int(r["vec_idx"]), r["platform"], PLATFORM_EN.get(r["platform"], r["platform"]),
            int(r["year"]), int(r["month"]), r["period"], int(r["rank"]),
            r["title"], r["artist"], r["file"],
            norm(r["title"], drop_bracket=True),
            overlap_class(r["platform"], r["title"]),
        ])
    w(OUT / "songs.csv",
      ["song_id", "platform", "platform_en", "year", "month", "period", "rank",
       "title", "artist", "file", "title_norm", "overlap_class"],
      rows_songs)

    # ------------------------------------------------- 唯一歌表（去重后的曲库）
    uniq = defaultdict(lambda: {"platforms": set(), "n": 0, "title": "", "artist": "", "file": ""})
    for r in vidx:
        v = int(r["vec_idx"])
        u = uniq[v]
        u["platforms"].add(r["platform"])
        u["n"] += 1
        u["title"], u["artist"], u["file"] = r["title"], r["artist"], r["file"]
    rows_u = []
    for v in sorted(uniq):
        u = uniq[v]
        pf_one = sorted(u["platforms"])[0]
        rows_u.append([v, u["title"], u["artist"],
                       "|".join(sorted(PLATFORM_EN.get(p, p) for p in u["platforms"])),
                       u["n"], u["file"], overlap_class(pf_one, u["title"])])
    w(OUT / "songs_unique.csv",
      ["song_id", "title", "artist", "platforms", "n_appearances", "file", "overlap_class"],
      rows_u)

    # ------------------------------------------- PCA 坐标（R 画二维图只要这个）
    pca = A["pca"]
    Vt = np.array(pca["axis"], dtype=np.float64)   # (k, 512)
    k = min(10, Vt.shape[0])
    mu = E.mean(axis=0)
    P = (E - mu) @ Vt[:k].T                        # (N, k)
    hdr = ["song_id", "title", "artist", "platform", "year", "month", "period", "rank"] + \
          [f"PC{i+1}" for i in range(k)]
    rows_pc = []
    for r in vidx:
        v = int(r["vec_idx"])
        rows_pc.append([v, r["title"], r["artist"], PLATFORM_EN.get(r["platform"], r["platform"]),
                        int(r["year"]), int(r["month"]), r["period"], int(r["rank"])] +
                       [round(float(x), 6) for x in P[v]])
    w(OUT / "vectors.csv", hdr, rows_pc)

    rows_pv = [[i + 1, round(float(e), 6)] for i, e in enumerate(pca["explained"][:k])]
    w(OUT / "pca_var.csv", ["pc", "explained_var"], rows_pv)

    # ------------------------------------------------------------- 质心（PC 空间）
    # 用单位向量平均 → 归一化，再投影到 PC 轴，和 Python 端口径完全一致
    def cen_pc(idx: list[int]) -> np.ndarray:
        v = E[idx].mean(axis=0)
        n = np.linalg.norm(v)
        return ((v / n) - mu) @ Vt[:k].T

    by = defaultdict(list)
    for r in vidx:
        by[(r["platform"], int(r["year"]))].append(int(r["vec_idx"]))
    rows_c = []
    for (pf, yr), idx in sorted(by.items()):
        c = cen_pc(sorted(set(idx)))
        rows_c.append([PLATFORM_EN.get(pf, pf), yr, len(set(idx))] +
                      [round(float(x), 6) for x in c])
    w(OUT / "centroid_pc.csv",
      ["platform", "year", "n_songs"] + [f"PC{i+1}" for i in range(k)],
      rows_c)

    mby = defaultdict(list)
    for r in vidx:
        mby[(r["platform"], r["period"])].append(int(r["vec_idx"]))
    rows_m = []
    for (pf, pe), idx in sorted(mby.items()):
        c = cen_pc(sorted(set(idx)))
        # QQ 的 period 是 "2018-08"，网易云是 "2018" —— 两种都要吃得下
        if "-" in pe:
            yr, mo = pe[:4], int(pe[5:7])
        else:
            yr, mo = pe, ""
        rows_m.append([PLATFORM_EN.get(pf, pf), pe, yr, mo, len(set(idx))] +
                      [round(float(x), 6) for x in c])
    w(OUT / "monthly_pc.csv",
      ["platform", "period", "year", "month", "n_songs"] + [f"PC{i+1}" for i in range(k)],
      rows_m)

    # --------------------------------------------------------- Q1 指标（长表）
    q1 = A["Q1_platform_diff"]
    rows_q1 = []

    def add_q1(metric, platform, value, lo=None, hi=None, note=""):
        rows_q1.append([metric, platform, value, lo, hi, note])

    add_q1("centroid_angle_deg", "both", round(q1["centroid_angle_deg"], 4),
           None, None, "angle between full-period centroids of the two platforms")
    add_q1("centroid_cosine", "both", round(q1["centroid_cosine"], 6))
    add_q1("within_lib_mean_cosine", "QQ Music", round(q1.get("compact_qq", float("nan")), 4),
           None, None, "mean pairwise cosine among QQ library songs")
    add_q1("within_lib_mean_cosine", "NetEase Cloud Music",
           round(q1.get("compact_ne", float("nan")), 4),
           None, None, "mean pairwise cosine among NetEase library songs")
    for d in q1.get("per_year_cross", []):
        add_q1("same_year_centroid_angle_deg", str(d.get("year", "")),
               round(float(d.get("angle_deg", float("nan"))), 4),
               None, None,
               f"n_qq={d.get('n_qq','')} n_ne={d.get('n_ne','')}")
    add_q1("single_song_auc", "QQ vs NetEase", round(q1["auc_qq_vs_ne"], 4),
           None, None, "Mann-Whitney AUC of per-song margin; 0.5 = indistinguishable")
    add_q1("margin_mean", "QQ Music", round(q1["margin_mean_qq"], 6))
    add_q1("margin_mean", "NetEase Cloud Music", round(q1["margin_mean_ne"], 6))
    add_q1("margin_sd", "both", round(q1["margin_std"], 6))
    add_q1("n_records", "QQ Music", int(q1["n_qq"]))
    add_q1("n_records", "NetEase Cloud Music", int(q1["n_ne"]))
    add_q1("n_unique_songs", "QQ Music", int(q1["uniq_qq"]))
    add_q1("n_unique_songs", "NetEase Cloud Music", int(q1["uniq_ne"]))
    w(OUT / "metrics_q1.csv",
      ["metric", "scope", "value", "ci_lo", "ci_hi", "note"], rows_q1)

    # --------------------------------------------------- Q2 年度漂移（含噪声带）
    rows_dr = []
    for pf, blob in A["Q2_temporal"].items():
        for d in blob.get("year_drift", []):
            rows_dr.append([PLATFORM_EN.get(pf, pf), int(d["from"]), int(d["to"]),
                            round(float(d["angle_deg"]), 4),
                            int(d.get("n_from", 0)), int(d.get("n_to", 0))])
    w(OUT / "drift_annual.csv",
      ["platform", "year_from", "year_to", "drift_deg", "n_from", "n_to"], rows_dr)

    # --------------------------------------------------- 月度粒度（QQ 独有）
    rows_mo = []
    for pf, blob in A["Q2_temporal"].items():
        for d in blob.get("cumulative", []):
            rows_mo.append([PLATFORM_EN.get(pf, pf), d["period"], str(d["period"])[:4],
                            int(d["n"]), round(float(d["angle_to_first_deg"]), 4)])
    w(OUT / "monthly_drift.csv",
      ["platform", "period", "year", "n_songs", "angle_to_first_deg"], rows_mo)

    # --------------------------------------------------- 年度结构（离散度/中文占比）
    rows_st = []
    for pf, blob in A["Q2_temporal"].items():
        lang = {d["year"]: d for d in blob.get("language", [])}
        for d in blob.get("spread", []):
            L = lang.get(d["year"], {})
            rows_st.append([PLATFORM_EN.get(pf, pf), int(d["year"]), int(d["n"]),
                            round(float(d["mean_pairwise_cosine"]), 4),
                            L.get("chinese_title", ""), L.get("chinese_title_pct", ""),
                            L.get("non_chinese_title", "")])
    w(OUT / "year_structure.csv",
      ["platform", "year", "n_songs", "mean_pairwise_cosine",
       "chinese_title_n", "chinese_title_pct", "non_chinese_title_n"], rows_st)

    # ----------------------------------------------------------- 覆盖率
    rows_cov = []
    for d in cov.get("by_year", []):
        rows_cov.append([PLATFORM_EN.get(d["platform"], d["platform"]), int(d["year"]),
                         int(d["hit"]), int(d["total"]), round(float(d["rate"]), 2)])
    w(OUT / "coverage.csv",
      ["platform", "year", "hits", "in_chart", "rate_pct"], rows_cov)

    rows_sum = []
    for pf, d in cov.get("summary", {}).items():
        rows_sum.append([PLATFORM_EN.get(pf, pf), int(d["rows_total"]), int(d["rows_hit"]),
                         int(d["uniq_total"]), int(d["uniq_hit"]),
                         round(100.0 * d["rows_hit"] / max(d["rows_total"], 1), 2),
                         round(100.0 * d["uniq_hit"] / max(d["uniq_total"], 1), 2)])
    w(OUT / "coverage_summary.csv",
      ["platform", "rows_total", "rows_hit", "uniq_total", "uniq_hit",
       "row_rate_pct", "uniq_rate_pct"], rows_sum)

    # ------------------------------------------------- 探针歌：《雪 Distance》
    # 窗口两两余弦要现算（analysis.json 没存），这样 R 端能独立复现原理链图
    pr = A["probe_song"]
    vi = int(pr["vec_idx"])
    audio = ROOT / "data" / "raw" / "audio" / "netease" / Path(pr["file"]).name
    wmat, n_win, dur = None, 0, 0.0
    try:
        import sys
        # 复用 build_vectors.py 里的 CLAP_VECTORIZER 定位逻辑
        sys.path.insert(0, str(CLAPV))
        import clapv
        eng = clapv.ClapEngine()
        wins = clapv.iter_windows(str(audio), clapv.SAMPLE_RATE, 10.0, 10.0, 0.0)
        n_win = len(wins)
        dur = clapv.probe_duration(str(audio))
        W = np.asarray(eng.embed_windows(wins, show_progress=False), dtype=np.float64)
        Wn = W / np.linalg.norm(W, axis=1, keepdims=True)
        wmat = np.clip(Wn @ Wn.T, -1, 1)
        same = float(np.dot(Wn.mean(axis=0) / np.linalg.norm(Wn.mean(axis=0)), E[vi]))
        print(f"  [probe] 窗口数={n_win} 时长={dur:.1f}s  与库内存向量一致性={same:.8f}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [probe] 现算窗口矩阵失败（{type(exc).__name__}: {exc}）")

    rows_pm = [[pr["title"], pr["artist"], PLATFORM_EN.get(pr["platform"], pr["platform"]),
                pr["period"], int(pr["rank"]), Path(pr["file"]).name,
                n_win, round(dur, 2),
                round(float(np.mean(np.clip(E @ E[vi], -1, 1))), 6)]]
    w(OUT / "probe_meta.csv",
      ["title", "artist", "platform", "period", "rank", "file",
       "n_windows", "duration_sec", "mean_cos_in_lib"], rows_pm)

    if wmat is not None:
        rows_w = []
        for i, row in enumerate(wmat):
            for j, c in enumerate(row):
                rows_w.append([i + 1, j + 1, round(float(c), 6)])
        w(OUT / "probe_chain.csv", ["window_i", "window_j", "cosine"], rows_w)

    # -------------------------------------------------------- 相似度直方图原料
    sims = np.clip(E @ E[vi], -1, 1)
    rows_sim = [[i, float(s)] for i, s in enumerate(sims)]
    w(OUT / "probe_similarity.csv", ["song_id", "cosine_to_probe"], rows_sim)

    # --------------------------------------------------- 全部两两相似度（库内紧致度）
    # 386×386 = 148k 行，可接受；R 端画分布用
    G = np.clip(E @ E.T, -1, 1)
    iu = np.triu_indices(len(E), k=1)
    rows_pair = [[int(a), int(b), round(float(G[a, b]), 5)] for a, b in zip(*iu)]
    w(OUT / "pairwise_cosine.csv", ["song_i", "song_j", "cosine"], rows_pair)

    # --------------------------------------------------- 单曲 margin（R 端自助法用）
    # margin = cos(song, QQ质心) - cos(song, 网易云质心)。
    # 分析单元 = 歌曲：每平台 × 每首歌一行（按 platform+vec_idx 去重，319+55=374 行），
    # 与 analyze.py 的 AUC 口径严格一致——重复上榜不重复计数，上榜次数不加权；
    # 质心同样按歌曲级（set 去重）计算。
    cq_i = sorted({int(r["vec_idx"]) for r in vidx if r["platform"] == "QQ音乐"})
    cn_i = sorted({int(r["vec_idx"]) for r in vidx if r["platform"] == "网易云"})
    cq5, cn5 = E[cq_i].astype(np.float64).mean(axis=0), E[cn_i].astype(np.float64).mean(axis=0)
    cq5, cn5 = cq5 / np.linalg.norm(cq5), cn5 / np.linalg.norm(cn5)
    rows_mg, seen_pm = [], set()
    for r in vidx:
        v, p = int(r["vec_idx"]), r["platform"]
        if (p, v) in seen_pm:
            continue
        seen_pm.add((p, v))
        rows_mg.append([v, PLATFORM_EN.get(p, p),
                        round(float(E[v] @ cq5 - E[v] @ cn5), 8)])
    w(OUT / "margins.csv", ["song_id", "platform", "margin"], rows_mg)

    # 唯一歌 × 512 维向量（R 端自助法/质心分析用；按 song_id 去重）
    seen_ids = {}
    for r in vidx:
        seen_ids.setdefault(int(r["vec_idx"]), r)
    rows_512 = []
    for v in sorted(seen_ids):
        r = seen_ids[v]
        rows_512.append([v, r["title"], r["artist"],
                         PLATFORM_EN.get(r["platform"], r["platform"])] +
                        [round(float(x), 7) for x in E[v]])
    w(OUT / "song_vectors_512.csv",
      ["song_id", "title", "artist", "platform"] + [f"dim_{j+1}" for j in range(E.shape[1])],
      rows_512)

    # ============================== 原理链原料（R 只负责画，不负责算） ========
    try:
        import soundfile as sf
        from scipy import signal as sps

        x, sr_in = sf.read(str(audio), dtype="float32", always_2d=True)
        x = x.mean(axis=1)
        dur_full = len(x) / sr_in

        # 波形包络：每列取 min/max（视觉上与逐采样点画等价，文件小 3 个量级）
        ncol = 2700
        edges = np.linspace(0, len(x), ncol + 1, dtype=int)
        env = np.array([[x[edges[i]:edges[i + 1]].min(), x[edges[i]:edges[i + 1]].max()]
                        for i in range(ncol)])
        rows_wf = [[round(i * dur_full / ncol, 5), round(float(a), 5), round(float(b), 5)]
                   for i, (a, b) in enumerate(env)]
        w(OUT / "probe_waveform.csv", ["t_sec", "amp_min", "amp_max"], rows_wf)

        # 第 3 窗（与 deck 相同：跳过 intro）的 STFT + 对数梅尔
        seg = wins[min(2, n_win - 1)]
        f, tt, S = sps.spectrogram(seg, clapv.SAMPLE_RATE, nperseg=2048,
                                   noverlap=1536, window="hann")
        Sdb = 10 * np.log10(S + 1e-10)
        fmask = f <= 16000
        fs_, ts_ = np.where(fmask)[0][::4], np.arange(0, Sdb.shape[1], 4)
        rows_st = [[int(k), round(float(tt[j]), 4), round(float(f[i] / 1000), 4),
                    round(float(Sdb[i, j]), 3)]
                   for k, j in enumerate(ts_) for i in fs_]
        w(OUT / "probe_stft.csv", ["frame", "t_sec", "freq_khz", "db"], rows_st)

        n_mels = 64

        def hz_to_mel(h): return 2595 * np.log10(1 + h / 700)  # noqa: E731
        def mel_to_hz(m): return 700 * (10 ** (m / 2595) - 1)  # noqa: E731

        mels = np.linspace(hz_to_mel(0), hz_to_mel(clapv.SAMPLE_RATE / 2), n_mels + 2)
        hz = mel_to_hz(mels)
        bins = np.floor((2048 + 1) * hz / clapv.SAMPLE_RATE).astype(int)
        fb = np.zeros((n_mels, 2048 // 2 + 1))
        for i in range(n_mels):
            l, c, r = bins[i], bins[i + 1], bins[i + 2]
            if c == l: c = l + 1
            if r == c: r = c + 1
            for j in range(l, min(c, fb.shape[1])):
                fb[i, j] = (j - l) / max(c - l, 1)
            for j in range(c, min(r, fb.shape[1])):
                fb[i, j] = (r - j) / max(r - c, 1)
        mel_db = 10 * np.log10(fb @ S + 1e-10)
        rows_mel = [[int(k), round(float(tt[j]), 4), int(i + 1),
                     round(float(mel_db[i, j]), 3)]
                    for k, j in enumerate(ts_) for i in range(n_mels)]
        w(OUT / "probe_mel.csv", ["frame", "t_sec", "mel_bin", "db"], rows_mel)

        # 17 个窗口的 512 维向量（宽表）——热图与「绝对值最大的维」都用它
        Wm = np.asarray(eng.embed_windows(wins, show_progress=False), dtype=np.float64)
        rows_wv = []
        for i, row in enumerate(Wm):
            rows_wv.append([i + 1] + [round(float(v), 6) for v in row])
        w(OUT / "probe_windows.csv",
          ["window"] + [f"dim_{j+1}" for j in range(Wm.shape[1])], rows_wv)
    except Exception as exc:  # noqa: BLE001
        print(f"  [chain] 原理链原料导出失败（{type(exc).__name__}: {exc}）")

    print("\nR 端数据已导出 →", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
