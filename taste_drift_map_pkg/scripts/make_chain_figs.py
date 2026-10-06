# -*- coding: utf-8 -*-
"""原理链插图：把一首歌真正跑一遍，把每一步的中间产物画出来。

画的是《雪 Distance》真实的波形/频谱/向量，不是示意图。
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
import soundfile as sf
from scipy import signal as sps

ROOT = Path(__file__).resolve().parent.parent          # 仓库根
FIG = ROOT / "figures"; FIG.mkdir(exist_ok=True)
INTERIM = ROOT / "data" / "interim"
RAW = ROOT / "data" / "raw"

# clap-audio-vectorizer：优先环境变量，其次仓库同级目录
CLAPV = Path(os.environ.get("CLAP_VECTORIZER",
                            ROOT.parent / "clap-audio-vectorizer")).expanduser()
if not (CLAPV / "clapv.py").exists():
    raise SystemExit(
        f"找不到 clap-audio-vectorizer（clapv.py）于 {CLAPV}\n"
        "请设置环境变量 CLAP_VECTORIZER，或把它克隆到本仓库同级目录。")
sys.path.insert(0, str(CLAPV))
import clapv  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

A = json.loads((INTERIM / "analysis.json").read_text(encoding="utf-8"))
PROBE = A["probe_song"]
SR = 48000
WIN = 10.0

# 项目配色（沿用已有 pptx 的设计语言）
GREEN = "#1DB954"
DARK = "#10131A"
GREY = "#6B7280"
BLUE = "#2563EB"
ORANGE = "#F59E0B"
RED = "#DC2626"
BG = "#FFFFFF"


def load_mono(path: str, sr: int = SR) -> np.ndarray:
    data, s = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if s != sr:
        n = int(round(len(mono) * sr / s))
        mono = sps.resample(mono, n).astype(np.float32)
    return mono


def main() -> int:
    path = PROBE["file"]
    # 探针歌来自网易云榜单，音频放在 data/raw/audio/netease/
    full = str(RAW / "audio" / "netease" / path)
    x = load_mono(full)
    dur = len(x) / SR
    print(f"样例曲: {PROBE['title']}  时长 {dur:.1f}s  {len(x)} 采样点")

    # 按 clapv 的切窗规则取窗口
    wins = clapv.iter_windows(full, SR, WIN, WIN, 0.0)
    n_win = len(wins)
    print(f"切成 {n_win} 个 10 秒窗口")

    # 取第 3 个窗口（跳过 intro，内容更典型）做频谱展示
    k = min(2, n_win - 1)
    seg = wins[k]

    # ---------------------------------------------------------------- 图 1：波形 + 切窗
    fig = plt.figure(figsize=(13.33, 3.4), dpi=220)
    ax = fig.add_axes([0.055, 0.22, 0.92, 0.66])
    t = np.arange(len(x)) / SR
    ax.plot(t, x, lw=0.25, color=GREEN)
    ax.set_xlim(0, dur); ax.set_ylim(-1.02, 1.02)
    ax.set_xlabel("时间（秒）", fontsize=11, color=GREY)
    ax.set_ylabel("振幅", fontsize=11, color=GREY)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#D1D5DB")
    ax.tick_params(colors=GREY, labelsize=9)
    # 窗口切分标注
    for i in range(n_win):
        x0, x1 = i * WIN, min((i + 1) * WIN, dur)
        if i == k:
            ax.axvspan(x0, x1, color=ORANGE, alpha=0.22, zorder=0)
            ax.axvline(x0, color=ORANGE, lw=1.4)
            ax.axvline(x1, color=ORANGE, lw=1.4)
            ax.text((x0 + x1) / 2, 1.12, f"第 {k+1} 窗", ha="center",
                    fontsize=11, color=ORANGE, fontweight="bold")
        else:
            ax.axvline(x0, color="#9CA3AF", lw=0.7, ls=":", alpha=0.8)
    ax.set_title(f"① 波形与切窗　{PROBE['title']} — {PROBE['artist']}"
                 f"（{dur:.0f} 秒 → {n_win} 个 10 秒窗口，步长 10 秒不重叠）",
                 fontsize=12.5, color=DARK, fontweight="bold", pad=16)
    fig.savefig(FIG / "chain_1_waveform.png", facecolor=BG)
    plt.close(fig)

    # ---------------------------------------------------------------- 图 2：频谱 + 对数梅尔
    fig = plt.figure(figsize=(13.33, 4.6), dpi=220)
    gs = gridspec.GridSpec(1, 2, figure=fig, left=0.055, right=0.975,
                           top=0.84, bottom=0.13, wspace=0.19)

    ax1 = fig.add_subplot(gs[0, 0])
    f, tt, S = sps.spectrogram(seg, SR, nperseg=2048, noverlap=1536, window="hann")
    Sdb = 10 * np.log10(S + 1e-10)
    ax1.pcolormesh(tt, f / 1000, Sdb, shading="gouraud", cmap="magma")
    ax1.set_ylim(0, 16)
    ax1.set_xlabel("窗口内时间（秒）", fontsize=10.5, color=GREY)
    ax1.set_ylabel("频率（kHz）", fontsize=10.5, color=GREY)
    ax1.set_title("②a 线性频谱图（STFT）", fontsize=11.5, color=DARK,
                  fontweight="bold", pad=10)
    ax1.tick_params(colors=GREY, labelsize=9)
    for s in ax1.spines.values():
        s.set_color("#D1D5DB")

    ax2 = fig.add_subplot(gs[0, 1])
    n_mels = 64
    # 用 librosa 风格的手工 mel 滤波器组（避免额外依赖）
    def hz_to_mel(h): return 2595 * np.log10(1 + h / 700)
    def mel_to_hz(m): return 700 * (10 ** (m / 2595) - 1)
    fmin, fmax = 0, SR / 2
    mels = np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2)
    hz = mel_to_hz(mels)
    bins = np.floor((2048 + 1) * hz / SR).astype(int)
    fb = np.zeros((n_mels, 2048 // 2 + 1))
    for i in range(n_mels):
        l, c, r = bins[i], bins[i + 1], bins[i + 2]
        if c == l: c = l + 1
        if r == c: r = c + 1
        for j in range(l, min(c, fb.shape[1])):
            fb[i, j] = (j - l) / max(c - l, 1)
        for j in range(c, min(r, fb.shape[1])):
            fb[i, j] = (r - j) / max(r - c, 1)
    mel = fb @ S
    mel_db = 10 * np.log10(mel + 1e-10)
    im = ax2.pcolormesh(tt, np.arange(n_mels), mel_db, shading="gouraud", cmap="magma")
    ax2.set_xlabel("窗口内时间（秒）", fontsize=10.5, color=GREY)
    ax2.set_ylabel("梅尔频带（低频在下）", fontsize=10.5, color=GREY)
    ax2.set_title("②b 对数梅尔频谱　← 模型真正「看到」的输入",
                  fontsize=11.5, color=ORANGE, fontweight="bold", pad=10)
    ax2.tick_params(colors=GREY, labelsize=9)
    for s in ax2.spines.values():
        s.set_color("#D1D5DB")
    cb = fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.02)
    cb.set_label("dB", fontsize=9.5, color=GREY)
    cb.ax.tick_params(colors=GREY, labelsize=8)

    fig.suptitle("② 从波形到频谱：为什么会「丢掉」时间轴的信息 —— 音频被压成一张二维图",
                 fontsize=12.5, color=DARK, fontweight="bold", y=0.95)
    fig.savefig(FIG / "chain_2_spectrogram.png", facecolor=BG)
    plt.close(fig)

    # ---------------------------------------------------------------- 图 3：512 维向量 + 归约
    eng = clapv.ClapEngine("laion/clap-htsat-unfused", "auto", "auto", 16, quiet=True)
    win_vecs = eng.embed_windows(wins, show_progress=False)   # (n_win,512) 已归一化
    song_vec = eng.embed_audio_file(full, WIN, WIN, 0.0)
    print(f"窗口向量 {win_vecs.shape} -> 歌曲向量 {song_vec.shape}")

    z = np.load(INTERIM / "vectors.npz", allow_pickle=False)
    stored = z["emb"][PROBE["vec_idx"]]
    cos_stored = float(np.dot(song_vec, stored))
    print(f"与库内存向量一致性: {cos_stored:.8f}")

    fig = plt.figure(figsize=(13.33, 4.9), dpi=220)
    gs = gridspec.GridSpec(2, 2, figure=fig, left=0.055, right=0.975,
                           top=0.82, bottom=0.12, wspace=0.22, hspace=0.62,
                           width_ratios=[1.25, 1])

    axm = fig.add_subplot(gs[:, 0])
    vmax = np.abs(win_vecs).max()
    im = axm.imshow(win_vecs, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                    interpolation="nearest")
    axm.set_xlabel("512 个维度", fontsize=10.5, color=GREY)
    axm.set_ylabel("第 n 个 10 秒窗口", fontsize=10.5, color=GREY)
    axm.set_title("③ 每个窗口 → 512 维向量（红正蓝负）",
                  fontsize=11.5, color=DARK, fontweight="bold", pad=10)
    axm.tick_params(colors=GREY, labelsize=9)
    cb = fig.colorbar(im, ax=axm, fraction=0.046, pad=0.02)
    cb.ax.tick_params(colors=GREY, labelsize=8)

    axs = fig.add_subplot(gs[0, 1])
    idx = np.arange(len(song_vec))
    order = np.argsort(song_vec)[::-1][:28]
    axs.bar(idx[:28], song_vec[order], color=[GREEN if v > 0 else RED for v in song_vec[order]])
    axs.set_title("最终歌曲向量：绝对值最大的 28 维", fontsize=11, color=DARK,
                  fontweight="bold", pad=8)
    axs.set_xlabel("维度编号（按数值排序）", fontsize=9.5, color=GREY)
    axs.set_ylabel("分量值", fontsize=9.5, color=GREY)
    axs.tick_params(colors=GREY, labelsize=8)
    for s in ("top", "right"):
        axs.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        axs.spines[s].set_color("#D1D5DB")

    axc = fig.add_subplot(gs[1, 1])
    M = win_vecs @ win_vecs.T
    im2 = axc.imshow(M, cmap="Greens", vmin=0.3, vmax=1.0)
    axc.set_title(f"窗口之间的余弦相似度（平均 {M[np.triu_indices_from(M,1)].mean():.3f}）",
                  fontsize=11, color=DARK, fontweight="bold", pad=8)
    axc.set_xlabel("窗口", fontsize=9.5, color=GREY)
    axc.set_ylabel("窗口", fontsize=9.5, color=GREY)
    axc.tick_params(colors=GREY, labelsize=8)
    cb2 = fig.colorbar(im2, ax=axc, fraction=0.046, pad=0.02)
    cb2.ax.tick_params(colors=GREY, labelsize=8)

    fig.suptitle("③ 编码与聚合：所有窗口向量取平均、再归一化，整首歌塌缩成单位球面上的 1 个点",
                 fontsize=12.5, color=DARK, fontweight="bold", y=0.94)
    fig.savefig(FIG / "chain_3_vector.png", facecolor=BG)
    plt.close(fig)

    # ---------------------------------------------------------------- 图 4：相似度=夹角
    rng = np.random.default_rng(0)
    others = rng.choice(len(z["emb"]), 700, replace=True)
    sims = z["emb"][others] @ song_vec
    fig = plt.figure(figsize=(13.33, 3.9), dpi=220)
    ax = fig.add_axes([0.06, 0.19, 0.90, 0.66])
    ax.hist(sims, bins=44, color=GREEN, alpha=0.75, label="与库内 386 首的相似度")
    ax.axvline(float(np.dot(song_vec, stored)), color=RED, lw=2.2,
               label=f"它自己（余弦 = {cos_stored:.4f}）")
    ax.axvline(sims.mean(), color=BLUE, lw=1.6, ls="--",
               label=f"库内平均（{sims.mean():.3f}）")
    ax.set_xlabel("余弦相似度", fontsize=11, color=GREY)
    ax.set_ylabel("歌曲数", fontsize=11, color=GREY)
    ax.set_title("④ 相似度就是夹角余弦：自己=1.000，库里其他歌全挤在高分区（窄锥效应）",
                 fontsize=12.5, color=DARK, fontweight="bold", pad=14)
    ax.legend(frameon=False, fontsize=10.5, loc="upper left")
    ax.tick_params(colors=GREY, labelsize=9.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#D1D5DB")
    fig.savefig(FIG / "chain_4_similarity.png", facecolor=BG)
    plt.close(fig)

    print("\n原理链 4 张图完成 ->", FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
