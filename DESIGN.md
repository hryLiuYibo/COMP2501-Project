# 设计文档：五年来国内网民听歌品味变迁分析

> 团队内部文档，仅中文
>
> 与 README.md 的关系：README 是英文公开版本（给评审老师、GitHub 访客），本文档记录"为什么这样做、坑在哪、谁负责什么"。

---

## 0. v2 重大变更（2026-09-21）

| 主题 | v1 设计 | v2 实际 | 原因 |
| --- | --- | --- | --- |
| **语言栈** | Python（爬虫 + 音频预处理）+ R（分析） | **R only** | 课程以 R 为主，是否允许 Python 表述模糊，避免风险 |
| 抓榜单实现 | 本地 Node `NeteaseCloudMusicApi` 后端 + Python requests | **R `httr` + `rvest` + `jsonlite`** | 原仓库 Binaryify/NeteaseCloudMusicApi 已停维，只剩"不再维护" |
| 音频特征 | Jukemir / MusicNN / CLAP 预训练模型（PyTorch） | **tuneR::melfcc + 自实现 spectral / chroma + seewave::timer/zcr** | 预训练模型都在 PyTorch，纯 R 栈拿不到 |
| 数据目录 | `data-pipeline/`（Python） | **`R/`** | 同上 |
| song_id 精度 | `int`（song_id < 2^31） | **字符串** | 实际 song_id 在 10^9 量级，超过 32-bit int 上限 |

**核心结论**：项目**不再使用 Python**。所有 .py 文件已删除，README.md 和本文件已同步更新。

---

## 1. 项目一句话

抓取 2020–2025 五年内网易云音乐每周热歌榜 Top 100，对每首歌抽音频特征向量（MFCC + spectral + chroma + tempo + ZCR，共 30 维），做时间序列上的聚类与降维分析，回答"国内网民的听歌品味在这五年里发生了什么变化"。

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                数据流水线（一次性建库，5 步）                    │
└─────────────────────────────────────────────────────────────┘

Step 1  ──►  Step 2  ──►  Step 3  ──►  Step 4  ──►  Step 5
抓榜单     下载 ncm     转 mp3 (CLI)    抽向量     清理 mp3
R/httr    (手动/wget)   R/system2     R/tuneR+   shell
                                   seewave

最终交付：data/embeddings/song_features.csv  (song_id × 30 维向量)
         data/raw/weekly_top100/*.json        (榜单元数据)
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                  分析层（持续迭代）                            │
└─────────────────────────────────────────────────────────────┘
       R Markdown notebooks (R/analysis/*.Rmd)
       ↓
  EDA → PCA/UMAP 降维 → 聚类 → 时序分析 → 报告
```

**关键设计原则：**
- 每一步独立可重跑，产物落盘
- 音频文件不上 git、不上传、不分发（隐私 + 法律）
- **单语言栈**：只用 R（除 ncmdump.exe 是外部 CLI 二进制）

---

## 3. 数据流与文件结构

```
data/
├── raw/
│   ├── weekly_top100/        # 每周榜单快照（.gitignore）
│   │   ├── 2020-W01.json     # {week, snapshot_time, songs: [...]}
│   │   ├── 2020-W02.json
│   │   └── ...               # 总计 ~260 个文件
│   └── songs_catalog.json    # 去重后的歌曲字典（id → 元数据），待写
│
├── ncm/                       # 临时，.gitignore
│   └── {song_id}.ncm
│
├── mp3/                       # 临时，.gitignore
│   └── {song_id}.mp3
│
└── embeddings/                # 长期保存（除 weights/cache 外可入仓）
    ├── song_features.csv          # song_id × 30 维特征向量（入仓）
    ├── song_features_failures.csv # 抽取失败的歌曲 + 原因（入仓，审计用）
    └── all_snapshots.rds          # 解析后的全榜单元数据 R 二进制（入仓）
```

### 3.1 weekly_top100/YYYY-WW.json schema

```json
{
  "week": "2026-W39",
  "snapshot_time": "2026-09-21T20:12:19+0800",
  "platform": "netease",
  "chart_id": 3778678,
  "n_songs": 100,
  "songs": [
    {
      "rank": 1,
      "song_id": "3342319503",        ← 字符串（防止精度丢失）
      "name": "明知故犯",
      "artists": ["Max李玄"],
      "duration_ms": 166416,
      "score": 100
    },
    ...
  ]
}
```

> **注意**：`snapshot_time` 是"我们抓到这份榜单的时刻"，**不是榜单本身的发布时间**。网易云不公开每周榜单的历史归档。`week` 字段是这次查询当天的 ISO 周。

### 3.2 song_features.csv schema

```
song_id,mfcc_1,...,mfcc_13,spec_centroid,spec_bandwidth,spec_flatness,C,C#,D,D#,E,F,F#,G,G#,A,A#,B,tempo,zcr
"3342319503",57.23,19.65,...,1.41,441.5,108.4,0.0005,...,0.98,NA,0.0235
```

30 维特征向量：

- `mfcc_1..mfcc_13`：13 维 MFCC（tuneR::melfcc）
- `spec_centroid`, `spec_bandwidth`, `spec_flatness`：3 维频谱描述（自实现 FFT）
- `C..B`：12 维 chroma（自实现 FFT + bin folding）
- `tempo`：节拍（BPM，seewave::timer）
- `zcr`：过零率（seewave::zcr）

### 3.3 歌曲去重规则

同一首歌在多个周榜里出现 → 只保留一个 song_id。`week × rank` 是榜单元数据，`song_id` 是去重键。

同一首 `song_id` 对应哪个具体版本（原唱 / 翻唱 / live）→ 取**最热门版本**（按全榜出现次数最多）。这一步在 R 端 `analysis/01_eda.Rmd` 里做。

---

## 4. Step 1：抓榜单（`R/fetch_weekly_top100.R`）

### 4.1 数据源策略（已实现 + 实测通过）

- **不**自己逆向 JS 签名（脆弱、易失效、灰色）—— 这正是 Binaryify/NeteaseCloudMusicApi 当初的方案，但作者已停维
- **不**用 Selenium / Puppeteer（重）
- **采用**：直接 `httr::GET()` 网易云热歌榜页面（`https://music.163.com/discover/toplist?id=3778678`）。页面是 SSR，HTML 里有一个 `<textarea id="song-list-pre-data">`，里面塞着完整的 Top 200 JSON 数组
- **解析**：`rvest::html_node("song-list-pre-data")` → `html_text()` → `jsonlite::fromJSON()`

实测（2026-09-21）：

```
HTTP 200, n_songs=200（取前 100）
song_id 精度保留（按字符串存）
中文 / 英文字段正常
```

### 4.2 反爬策略

- 单 IP 每分钟 ≤ 30 次请求（保守）
- 请求间 sleep 2-5 秒随机
- User-Agent 设为 Chrome 桌面端
- 失败重试 3 次（指数退避，5s 起步）
- 整个 5 年榜单一轮 ≈ 5 × 52 × 4 秒 ≈ 17 分钟

### 4.3 关键函数

```r
fetch_toplist_page()    # httr GET，3 次重试
extract_songs_json()    # rvest 定位 textarea + jsonlite 解析
song_to_row()           # 把 JSON 转成我们的 schema（song_id 走字符串）
iso_week_label()        # Date → "YYYY-Www"
parse_week_label()      # "YYYY-Www" → Date（周一）
save_snapshot()         # 落 JSON
```

---

## 5. Step 2：下载 .ncm（待写，外部工具）

- 输入：`data/songs_catalog.json`
- 来源：手动用第三方工具（网易云 PC 客户端 / 浏览器开发者工具抓 m3u8）下载 `{song_id}.ncm` 到 `data/ncm/`
- 失败重试 3 次
- **当前没写脚本**，因为写一个 ncm 直接下载器需要 JS 签名。短期内建议手动下载 / 用现成工具集

---

## 6. Step 3：本地 ncm → mp3 转换（`R/convert_ncm_to_mp3.R`）

- **不用 GUI 拖拽**：仓库里曾经放着的 `Ncm转mp3拖一拖.exe`（后改名为 `Trans.exe`）是 GUI 拖拽工具，不接受命令行参数，无法被脚本自动调用，所以**移出流水线**
- **改用 CLI 工具**：`R/convert_ncm_to_mp3.R` 调用社区 CLI 后端（`system2()`）
- **后端候选**：
  - [ncmdump](https://github.com/anonymous5l/ncmdump)（Go，单文件 exe，**推荐**）
  - [ncmdump-py](https://github.com/giant-app/ncmdump-py)（`pip install`，Python wrapper）
- **抽象层**：S4 类 `NcmConverter` + 两个具体子类 `NcmdumpCliConverter` / `NcmdumpPyConverter`，换后端只改 `--backend` 参数

```bash
# 后端 1（推荐）：ncmdump.exe
Rscript R/convert_ncm_to_mp3.R \
    --src data/ncm --dst data/mp3 \
    --backend ncmdump --exe path/to/ncmdump.exe

# 后端 2：ncmdump-py
Rscript R/convert_ncm_to_mp3.R \
    --src data/ncm --dst data/mp3 \
    --backend ncmdump-py
```

- **断点续跑**：已存在的 `.mp3` 自动跳过
- **批量转换耗时**：ncmdump 通常 1-3 秒/首

---

## 7. Step 4：mp3 → 特征向量（`R/extract_audio_features.R`）

### 7.1 为什么不用预训练模型

v1 设计里推荐 Jukemir / MusicNN / CLAP。这些模型都在 PyTorch 里：

| 模型 | 维度 | 大小 | 依赖 |
| --- | --- | --- | --- |
| Jukemir | 4800 | ~1 GB | PyTorch + Jukebox |
| MusicNN | 128 | ~50 MB | TensorFlow / ONNX |
| CLAP | 512 | ~400 MB | PyTorch + laion-clap |

切到纯 R 栈后**完全无法使用**（即便 `reticulate` 包桥接，也容易坏且违背"单语言"原则）。

### 7.2 替代方案：经典 MIR 描述子

30 维手工特征向量：

- **13 维 MFCC**：`tuneR::melfcc()`（包自带，原始 kaldi 实现）
- **3 维 spectral**（centroid / bandwidth / flatness）：自实现 FFT + 加窗
- **12 维 chroma**：自实现 FFT + 12 个半音 bin folding
- **tempo**：`seewave::timer()`
- **zcr**：`seewave::zcr()`

**代价**：特征维度从 4800 降到 30，**没有"流派"这种高层语义**。但是：

- 30 维对 5 年 × 100 首 = 500 首歌的样本量来说完全够用
- 全部可解释（每个维度都有物理意义）
- 老师能从代码看出你懂 audio processing（不是 call 一个黑盒）

### 7.3 产出

- `data/embeddings/song_features.csv`（入仓）
- `data/embeddings/song_features_failures.csv`（入仓，审计用：哪些歌抽不出来 + 为什么）

---

## 8. Step 5：清理（手动）

抽完向量后，`rm -rf data/ncm data/mp3`（或 Windows 资源管理器删掉）。**不要让 mp3 长期存在**。

---

## 9. 分析层（R）

### 9.1 笔记本结构（建议）

```
R/analysis/
├── 01_eda.Rmd                     # 数据读入 + 描述统计 + 基础可视化
├── 02_dimension_reduction.Rmd     # PCA + UMAP 2D "音乐地图"
└── 03_temporal_drift.Rmd          # 时序分析（年度质心漂移）
```

`01_eda` 是当前优先级最高的 —— 一旦数据跑通，先做几个图就能看到 drift 的故事。

### 9.2 关键问题 → 对应分析

| 想知道 | 用什么方法 |
| --- | --- |
| "年度最平均歌" | 每年的特征均值 → 找最近邻 |
| "年度最特别歌" | 每首歌到年度均值的距离排名 |
| "听歌品味地图" | UMAP 降维到 2D |
| "流派自动归类" | K-means / 层次聚类（基于 30 维特征） |
| "五年主轴漂移" | PCA 主成分 → 时间序列 |
| "哪些维度变化最大" | 每年方差最大的几个 PCA 维度的载荷分析 |

---

## 10. 时间线

### 10.1 整体节奏

| 周次 | 任务 | 负责 | 状态 |
| --- | --- | --- | --- |
| W1 | 项目初始化 + 提案 | 两人共同 | ✅ 进行中 |
| W1 末 | 抓榜单脚本跑通（实测成功 2026-09-21） | 共同 | ✅ |
| W2 | 抓全 5 年榜单（~260 个快照）+ 下载 mp3 | 待定 | ⏳ |
| W2-W3 | ncm → mp3 转换 + 特征抽取 | 待定 | ⏳ |
| W3 | 合成 song_features.csv | 待定 | — |
| W3-W4 | R 端 EDA + 降维（出几张图） | 待定 | — |
| W4 | R 端聚类 + 时序分析 | 待定 | — |
| W5 | Proposal 撰写（**deadline: 9/28-9/30**） | 两人共同 | — |
| W6 | 报告 + 幻灯片初稿 | 两人共同 | — |
| W7 | Buffer + 排练 presentation | 两人共同 | — |

### 10.2 风险节点

- **9/28-9/30 Proposal 截止**：必须 W5 之前出初步结论，否则赶不上
- **抓榜单脚本 ✅ 跑通**：但要小心反爬封 IP（脚本支持断点续跑）
- **ncm 下载 ✅ 待工具**：考虑短期手动 / 长期写脚本

---

## 11. 风险 & 应对

| 风险 | 概率 | 应对 |
| --- | --- | --- |
| 网易云反爬封 IP | 中 | 限速 + 重试 + 断点续跑 |
| mp3 下载不到（有版权歌曲下架） | 中 | 跳过 + 标记 unavailable，最终向量化时排除 |
| 翻唱 / 版本归一搞不定 | 中 | 用最简单规则（出现频次最高的版本），R 端再清洗 |
| mp3 → 向量耗时过长 | 中 | 跑批处理脚本，留夜里跑；并发加速 |
| R 4.6 + tuneR/seewave 兼容性 | 低-中 | 当前测试通过；安装时若遇 C 编译问题可退到老版本 R |
| seewave API 变动（hanning → hanning.w 这种） | 中 | 在脚本里写死别名；**当前已处理** |
| 法律 / 合规 | 低-中 | 仅本地用 + 不分发，论文不公开 mp3，只公开向量 |

### 11.1 已踩过的坑（避免重复）

| 坑 | 表现 | 解决 |
| --- | --- | --- |
| NeteaseCloudMusicApi 仓库已被作者清空 | git clone 只拿到一个 README | 改用直接抓 SSR 页面 |
| song_id 在 `as.integer()` 后变 NA | id 超过 32-bit int 范围 | 全部按字符串存 |
| seewave 2.2.4 里 `mfcc` / `chroma` 不再导出 | NotImplementedError | 用 tuneR::melfcc + 自实现 chroma |
| seewave 2.2.4 里 `hanning` 改名为 `hanning.w` | could not find function | 用 `seewave::hanning.w()` |
| tuneR::melfcc 接收数值向量会失败 | Error swallowed by tryCatch | 必须传 Wave 对象 |

---

## 12. 法律 / 合规边界

| 操作 | 风险 |
| --- | --- |
| 抓榜单元数据（歌名 / 排名 / 歌手） | 公开信息，合理使用 |
| 下载 .ncm 到本地 | 灰色，但研究 + 自用通常没事 |
| .ncm → .mp3 本地转换 | 已有工具，转换过程本身合规 |
| mp3 → 特征向量 | 仅本地、临时、不分发 |
| 上传 mp3 到任何地方 | ❌ 不要做 |
| 在报告中放 mp3 内容 / 公开链接 | ❌ 不要做 |
| 把特征向量 + 元数据公开 | ✅ 可以 |

**重要**：所有 mp3 / ncm 用完即删。仓库里只允许出现 `song_features.csv`（数值矩阵）、`song_features_failures.csv`（失败审计）和 `weekly_top100/*.json`（榜单元数据）。

---

## 13. 待办 & 责任人

### 13.1 已完成

- [x] 初始化仓库
- [x] 写 README.md（v2 公开版）
- [x] 写 DESIGN.md（本文件 v2）
- [x] `R/fetch_weekly_top100.R` —— 实测 100 首歌抓取成功
- [x] `R/convert_ncm_to_mp3.R` —— 待 ncmdump.exe 实测
- [x] `R/extract_audio_features.R` —— 用合成信号验证全流程
- [x] 更新 `.gitignore`

### 13.2 立即可做

- [ ] 抓全 5 年榜单快照（约 260 个 .json）
- [ ] 下载 ncmdump.exe 到 `tools/` 外（比如 `~/tools/ncmdump.exe`）
- [ ] 写 `R/download_ncm.R`（或先用手动方式）
- [ ] 合成 `data/songs_catalog.json`
- [ ] 第一次 commit + push

### 13.3 中期 TODO

- [ ] `R/analysis/01_eda.Rmd` 把数据接入、出第一张图
- [ ] `R/analysis/02_dimension_reduction.Rmd` 跑 PCA + UMAP
- [ ] `R/analysis/03_temporal_drift.Rmd` 时序分析

### 13.4 长期 TODO

- [ ] Proposal 撰写（deadline 9/28-9/30）
- [ ] 论文初稿
- [ ] Slides
- [ ] Presentation 排练

---

## 14. 角色分工（建议）

| 任务 | 建议主负责 |
| --- | --- |
| 数据流水线（R/fetch, R/convert, R/extract） | 偏 R 工程的一方 |
| 分析 + 报告（R/analysis/*） | 偏 R / 统计的一方 |
| Proposal 撰写 | 共同 |
| Presentation 排练 | 共同 |

**关键原则**：双方都要理解每一行代码（Lec01 AI 政策）。

---

## 15. 变更记录

| 日期 | 版本 | 修改 |
| --- | --- | --- |
| 2026-09-07 | v1 | 初版（Python + Node + 预训练模型） |
| 2026-09-21 | v2 | 切到纯 R 栈：rvest + tuneR + seewave 经典特征，30 维；删除 data-pipeline/ |
