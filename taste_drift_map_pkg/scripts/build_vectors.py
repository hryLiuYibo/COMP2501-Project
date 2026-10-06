# -*- coding: utf-8 -*-
"""把匹配到的歌全部向量化，合成一个统一向量库（需要 GPU / PyTorch）。

依赖：
    clap-audio-vectorizer  —— https://github.com/<you>/clap-audio-vectorizer
    用环境变量 CLAP_VECTORIZER 指向它的目录（默认 ./clap-audio-vectorizer）：
        set CLAP_VECTORIZER=D:\\code\\clap-audio-vectorizer      # Windows
        export CLAP_VECTORIZER=~/code/clap-audio-vectorizer     # Linux / macOS

输入：data/interim/charts_matched.csv（由 build_matches.py 生成）
输出：
    data/interim/vectors.npz
        emb       (N, 512) float32, 已 L2 归一化
        files     (N,)     本地文件名
        paths     (N,)     本地绝对路径
        keys      (N,)     "平台|期次|歌名|本地文件" 的唯一键
        meta      (N,)     JSON 串（平台/年/月/排名/歌名/歌手/是否人工裁决）
    data/interim/per_song.csv       每首唯一歌一行：平台、标题、向量索引（供质心/轨迹计算）
    data/interim/vector_index.csv   每条榜单记录 -> 向量索引（可 1 对多）
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- 路径
ROOT = Path(__file__).resolve().parent.parent          # 仓库根
INTERIM = ROOT / "data" / "interim"
OUT = INTERIM

# clap-audio-vectorizer 的位置：优先读环境变量，其次找仓库同级目录
CLAPV = Path(os.environ.get("CLAP_VECTORIZER",
                            ROOT.parent / "clap-audio-vectorizer")).expanduser()
if not (CLAPV / "clapv.py").exists():
    raise SystemExit(
        f"找不到 clap-audio-vectorizer（clapv.py）于 {CLAPV}\n"
        "请设置环境变量 CLAP_VECTORIZER 指向它的目录，或把它克隆到本仓库同级目录。")
sys.path.insert(0, str(CLAPV))
import clapv  # noqa: E402


def main() -> int:
    rows = list(csv.DictReader(open(OUT / "charts_matched.csv", encoding="utf-8-sig")))
    hit = [r for r in rows if r["matched"] == "1"]
    print(f"榜单记录 {len(rows)} 条，命中 {len(hit)} 条")

    # ---- 唯一音频文件（同一首歌可能在多条榜单记录里出现） ----
    uniq: dict[str, dict] = {}
    for r in hit:
        p = r["path"]
        if p not in uniq:
            uniq[p] = {"path": p, "file": r["file"], "records": []}
        uniq[p]["records"].append(r)
    files_sorted = sorted(uniq.keys())
    print(f"涉及唯一音频文件 {len(files_sorted)} 个")

    eng = clapv.ClapEngine("laion/clap-htsat-unfused", "auto", "auto", 16, quiet=False)

    embs: list[np.ndarray] = []
    meta: list[str] = []
    keys: list[str] = []
    index_of: dict[str, int] = {}
    t0 = time.time()

    for i, p in enumerate(files_sorted, 1):
        u = uniq[p]
        try:
            v = eng.embed_audio_file(p, 10.0, 10.0, 0.0)
        except Exception as e:                                  # noqa: BLE001
            print(f"  [失败] {u['file']}: {e}")
            v = np.zeros(512, dtype=np.float32)
        embs.append(v)
        index_of[p] = len(embs) - 1
        rec = u["records"][0]
        keys.append(f"{rec['platform']}|{rec['title']}|{u['file']}")
        meta.append(json.dumps({
            "file": u["file"],
            "records": [{"platform": x["platform"], "period": x["period"],
                         "rank": x["rank"], "title": x["title"],
                         "artist": x["artist"], "how": x["match_how"]}
                        for x in u["records"]],
        }, ensure_ascii=False))

        if i % 20 == 0 or i == len(files_sorted):
            el = time.time() - t0
            sp = i / el if el else 0
            eta = (len(files_sorted) - i) / sp if sp else 0
            print(f"\r  {i}/{len(files_sorted)}  {sp:.2f} 首/s  ETA {eta/60:.1f} min   ",
                  end="", flush=True)
    print()

    E = np.stack(embs).astype(np.float32)
    nz = np.linalg.norm(E, axis=1)
    print(f"向量矩阵 {E.shape}，零向量(失败) {int((nz < 1e-6).sum())} 个")

    np.savez_compressed(OUT / "vectors.npz",
                        emb=E, files=np.array([uniq[p]["file"] for p in files_sorted], dtype=str),
                        keys=np.array(keys, dtype=str), meta=np.array(meta, dtype=str),
                        paths=np.array(files_sorted, dtype=str))

    # ---- 每条榜单记录 -> 向量索引 ----
    with open(OUT / "vector_index.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["platform", "year", "month", "rank", "period",
                                           "genre", "title", "artist", "file", "vec_idx"],
                           extrasaction="ignore")
        w.writeheader()
        for r in hit:
            r = dict(r)
            r["vec_idx"] = index_of[r["path"]]
            w.writerow(r)

    # ---- 每首唯一歌一行 ----
    with open(OUT / "per_song.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["vec_idx", "file", "platforms", "n_records", "path"])
        w.writeheader()
        for i, p in enumerate(files_sorted):
            u = uniq[p]
            w.writerow({
                "vec_idx": i, "file": u["file"],
                "platforms": "|".join(sorted({x["platform"] for x in u["records"]})),
                "n_records": len(u["records"]), "path": p,
            })

    print("写出: vectors.npz / vector_index.csv / per_song.csv")
    print(f"总耗时 {(time.time()-t0)/60:.1f} 分钟")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
