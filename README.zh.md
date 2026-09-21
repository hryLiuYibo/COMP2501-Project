# 五年来国内网民听歌品味变迁 — 网易云版

> COMP2501 数据科学导论 · 课程项目

一份基于网易云音乐"热歌榜"的**数据科学分析**：用过去 5 年的榜单数据观察国内网民听歌品味的变迁。每首歌都转成一个特征向量，再用降维 / 聚类 / 时序分析把它变成可视化的故事。

[English version](./README.en.md)

---

## 项目亮点

- **单一数据源** — 网易云音乐"热歌榜"，2020–2025，每周一快照
- **100% 纯 R 栈** — 抓取、转换、抽特征、分析全在 R 里完成（详见下方"技术栈"）
- **音频 → 向量** — 用经典 MIR 描述子：MFCC + 自实现 spectral / chroma + tempo + ZCR，共 30 维
- **本地处理** — `.ncm` 通过 CLI 工具 [ncmdump](https://github.com/taurusxin/ncmdump) 解密为 `.mp3`，抽完特征立刻删除，**不上传、不分发**

---

## 仓库结构

```
COMP2501-Project/
├── README.md                   # 英文默认（公开版）
├── README.en.md                # 英文版（与 README.md 内容相同，GitHub 自动切换）
├── README.zh.md                # 本文件（中文版）
├── TODO.md                     # 下一步要做什么（中文）
├── Proj_Proposal_Firstidea.md  # v1 项目提案（中文，团队内部）
├── DESIGN.md                   # 详细设计 + 流水线图 + 踩坑记录（中文）
├── .gitignore
│
├── R/                          # R 数据流水线 + 分析
│   ├── README.md               # R 子项目说明
│   ├── fetch_weekly_top100.R   # [1] 抓榜单（rvest + httr）
│   ├── convert_ncm_to_mp3.R    # [2] ncm → mp3（CLI 包装）
│   ├── build_songs_catalog.R   # [3] 生成 catalog 索引
│   ├── extract_audio_features.R# [4] mp3 → 30 维特征
│   └── analysis/               # [5] R Markdown 报告（EDA / 降维 / 漂移）
│
├── data/                       # 不入仓（见 .gitignore）
│   ├── raw/weekly_top100/      # 周榜单 JSON（gitignored）
│   ├── ncm/                    # 下载的 .ncm（临时）
│   ├── mp3/                    # 解出的 .mp3（临时）
│   ├── embeddings/             # song_features.csv（入仓）
│   └── songs_catalog.json      # 歌曲索引（入仓）
│
└── docs/                       # 报告 / slides（待写）
```

---

## 技术栈

| 层 | 工具 |
| --- | --- |
| 网页抓取 | R + `httr` + `rvest` + `jsonlite` |
| ncm → mp3 | R → `shell()` 调用 `ncmdump.exe`（不放仓库） |
| 音频解码 | R + `tuneR::readMP3()` |
| 音频特征 | R + `tuneR::melfcc()` + 自实现 FFT + `seewave::timer/zcr` |
| 数据分析 | R + `tidyverse` + `ggplot2` |
| 降维 | R + base `prcomp` + `uwot::umap`（待装） |
| 报告 | R Markdown |

**为什么是纯 R？** 课程以 R 为核心，语言边界模糊时默认 R 最稳。换语言不会让分析更好，只会让维护更难。

---

## 数据源

- **平台**：网易云音乐（music.163.com）
- **榜单**：热歌榜（chart_id = 3778678）
- **抓取策略**：榜单页是 SSR 服务端渲染的，前 200 首歌直接以 JSON 数组塞在 `<textarea id="song-list-pre-data">` 节点里。我们用 `httr::GET()` 抓页面 + `rvest` 解析 + `jsonlite` 解码，**不调有签名反爬的 `/api/v3/...` 接口**。
- **频率**：每周（一次快照 = 当前榜单状态）
- **歌曲数**：单快照前 100 首（页面实际返回前 200）
- **时间范围**：2020–2025（≈ 5 年 × 52 周 ≈ 260 个快照）
- **去重**：同周内 100 个 song_id 是不同歌曲；跨周去重后总歌曲数远小于 26000

> **重要**：网易云**不发布历史榜单**，榜单页是"滚动直播"。要拿 5 年数据，我们得在不同日期反复抓，每抓到一份就存为"那一周的快照"。详见 [DESIGN.md §3.1](./DESIGN.md)。

---

## 音频特征流水线

```
[1] R/fetch_weekly_top100.R    →  data/raw/weekly_top100/<YYYY-Www>.json
[2] (外部) 客户端下载 .ncm       →  data/ncm/<song_id>.ncm
[3] R/convert_ncm_to_mp3.R     →  data/mp3/<...>.mp3
[4] R/build_songs_catalog.R    →  data/songs_catalog.json
[5] R/extract_audio_features.R →  data/embeddings/song_features.csv
[6] 删除 .ncm + .mp3（仅留 csv 入仓）
```

**30 维特征向量**：

```
mfcc_1, ..., mfcc_13         (13 维 MFCC)
spec_centroid, spec_bandwidth, spec_flatness   (3 维频谱描述)
C, C#, D, D#, E, F, F#, G, G#, A, A#, B         (12 维 chroma)
tempo, zcr                                        (节拍 + 过零率)
```

详细设计、踩坑记录、未来优化见 [DESIGN.md](./DESIGN.md)。

---

## 怎么跑

### 一次性准备（已完成）

1. 装 R 包：`tuneR`、`seewave`、`httr`、`rvest`、`jsonlite`、`tidyverse`
2. 下载 `ncmdump.exe` 到 `~/tools/ncmdump/`（**不放仓库**，路径在 `R/convert_ncm_to_mp3.R --exe` 里指定）

### 每周抓一次榜单

```bash
Rscript R/fetch_weekly_top100.R --week auto --top 100 --out data/raw/weekly_top100
```

`--week auto` 用当前 ISO 周；也可指定 `--week 2025-W38`。

### 把已有的 .ncm 转成 .mp3

```bash
Rscript R/convert_ncm_to_mp3.R \
    --src data/ncm \
    --dst data/mp3 \
    --backend ncmdump \
    --exe "C:/Users/YourName/tools/ncmdump/ncmdump.exe"
```

自动跳过已存在的 mp3，可断点续跑。

### 生成 catalog + 抽特征

```bash
# 第一次：用 mp3 文件名生成 catalog
Rscript R/build_songs_catalog.R --mp3-dir data/mp3 --out data/songs_catalog.json

# 后续：可以加入从抓榜单抓到的 song_id 信息
Rscript R/build_songs_catalog.R \
    --snapshots data/raw/weekly_top100 \
    --mp3-dir   data/mp3 \
    --out       data/songs_catalog.json

# 抽特征
Rscript R/extract_audio_features.R \
    --src     data/mp3 \
    --catalog data/songs_catalog.json \
    --out     data/embeddings
```

### 看分析

```bash
# 用 RStudio 打开 R/analysis/01_eda.Rmd，knit 成 HTML
```

---

## 当前进度（截至 2026-09-21）

✅ **流水线打通**：抓榜单 → 转 mp3 → 建 catalog → 抽特征，3 首真实 mp3 全过。

⏳ **待办**：抓 5 年真实榜单 + 把分析 Rmd 接上数据 + 写 Proposal。详见 [TODO.md](./TODO.md)。

🚧 **已知坑**（全部记录在 DESIGN.md §11.1）：

- Windows + R 4.6.x 上 `list.files(pattern=...)` 会丢带逗号的文件名 → 用 `Sys.glob()`
- `seewave::resamp` 需要位置参数 `g` → 用 `tuneR::downsample` 替代
- 中文 Windows 上 `system2()` 调中文路径会编码失败 → 用临时 .bat + `shell()`
- ncmdump (cxxopts) 的 `-o` 必须在文件**之后**才生效
- ...

---

## 课程信息

- **课程**：COMP2501 数据科学导论，HKU SDS
- **占分**：30%（期末）
- **格式**：R Markdown 报告 + 10–20 min 演示，1–2 人组队
- **截止日期**：
  - 提案：2026-09-28 ~ 2026-09-30 11:59pm
  - 终期展示：待定
- **AI 政策**：LLM 辅助（含本 README）允许，但每行代码自己都要能讲清。LLM 生成的内容不要直接当作业交。

更详细的设计、踩坑、时间线见 [DESIGN.md](./DESIGN.md)；待办见 [TODO.md](./TODO.md)；原始提案见 [Proj_Proposal_Firstidea.md](./Proj_Proposal_Firstidea.md)。

---

## 团队 / 语言约定

- 团队：GitHub 上 2 位合作者
- 内部文档 / 设计 / TODO：**中文**
- README（公开版）/ commit message / R Markdown 报告：**英文**（与 GitHub 评审习惯一致）
- 用户公开版 README 提供中英双语：
  - 英文默认（`README.md`，与 `README.en.md` 同内容）
  - 中文版 `README.zh.md`（GitHub 自动识别并显示语言切换按钮）
