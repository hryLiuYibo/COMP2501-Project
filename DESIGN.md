# 设计文档：十年来国内网民听歌品味变迁分析

> 团队内部文档，仅中文
>
> 与 README.md 的关系：README 是英文公开版本（给评审老师、GitHub 访客），本文档记录"为什么这样做、坑在哪、谁负责什么"。

---

## 1. 项目一句话

抓取 2020–2025 五年内网易云音乐每周热歌榜 Top 100，对每首歌抽音频特征向量，做时间序列上的聚类与降维分析，回答"国内网民的听歌品味在这五年里发生了什么变化"。

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                数据流水线（一次性建库，5 步）                   │
└─────────────────────────────────────────────────────────────┘

Step 1  ──►  Step 2  ──►  Step 3  ──►  Step 4  ──►  Step 5
抓榜单     下载 ncm     本地转 mp3    抽向量     清理 mp3
Python     Python      手动 GUI     Python     shell
                   (Ncm转mp3
                    拖一拖.exe)

最终交付：data/embeddings/song_vectors.csv  (song_id × vector)
        data/raw/weekly_top100/*.json       (榜单元数据)
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                  分析层（持续迭代）                            │
└─────────────────────────────────────────────────────────────┘
       R Markdown notebooks (analysis/*.Rmd)
       ↓
  EDA → PCA/UMAP 降维 → 聚类 → 时序分析 → 报告
```

**关键设计原则：**
- 每一步独立可重跑，产物落盘
- 音频文件不上 git、不上传、不分发（隐私 + 法律）
- Python 只做"重工程"，R 做"重分析"

---

## 3. 数据流与文件结构

```
data/
├── raw/
│   ├── weekly_top100/        # 每周榜单快照
│   │   ├── 2020-W01.json     # {week, songs: [{rank, song_id, name, artists}]}
│   │   ├── 2020-W02.json
│   │   └── ...               # 总计 ~260 个文件
│   └── songs_catalog.json    # 去重后的歌曲字典（id → 元数据）
│
├── ncm/                       # 临时，.gitignore
│   └── {song_id}.ncm
│
├── mp3/                       # 临时，.gitignore
│   └── {song_id}.mp3
│
└── embeddings/                # 长期保存，可入仓（小）
    ├── song_vectors.csv       # song_id × [v_0, v_1, ..., v_D]
    └── song_metadata.csv      # song_id × 元数据
```

### 3.1 weekly_top100/YYYY-WW.json schema

```json
{
  "week": "2020-W01",
  "snapshot_time": "2026-09-08T20:30:00+08:00",
  "platform": "netease",
  "chart_id": 3778678,
  "songs": [
    {
      "rank": 1,
      "song_id": 1345863568,
      "name": "芒种",
      "artists": ["音阙诗听", "赵方婧"],
      "duration_ms": 235000
    },
    ...
  ]
}
```

> **注意**：`snapshot_time` 是"我们抓到这份榜单的时刻"，**不是榜单本身的发布时间**。网易云不公开每周榜单的历史归档，所以这个字段描述的是我们这次采集发生的时间。**真正作为时间标签的是 `week` 字段本身。**

### 3.2 song_vectors.csv schema

```
song_id,v_0,v_1,v_2,...,v_D
1345863568,0.123,-0.045,...,0.678
...
```

`D` 取决于 embedding 模型：
- Jukemir: 4800 维（太大，建议 PCA 后保留 50-100 维）
- MusicNN: 128 维- CLAP: 512 维

### 3.3 歌曲去重规则

同一首歌在多个周榜里出现 → 只保留一个 song_id。`week × rank` 是榜单元数据，`song_id` 是去重键。

同一首 `song_id` 对应哪个具体版本（原唱 / 翻唱 / live）→ 取**最热门版本**（按全榜出现次数最多）。

---

## 4. Step 1：抓榜单（fetch_weekly_top100.py）

### 4.1 数据源策略

- **不**自己逆向 JS 签名（脆弱、易失效、灰色）
- **不**用 Selenium（重）
- **方案 A（推荐）**：跑一个本地 [NeteaseCloudMusicApi](https://github.com/Binaryify/NeteaseCloudMusicApi) 服务（Node.js），用 HTTP 调用它暴露的 `/toplist/detail` 和 `/toplist` 接口
- **方案 B（备选）**：直接 Python `requests` 调 `music.163.com` 公开 web 接口（部分接口可匿名访问）

### 4.2 接口列表

| 用途 | 推荐接口 | 备注 |
| --- | --- | --- |
| 列出所有榜单 | `GET /toplist` | 获取 chart_id 列表 |
| 榜单歌曲详情 | `GET /toplist/detail?id={chart_id}` | 返回 Top 100 含 song_id |
| 单曲元数据 | `GET /song/detail?ids={id1,id2}` | 名字/歌手/时长/专辑 |
| 单曲下载 URL | `GET /song/url?id={id}&br=320000` | 返回 .ncm 直链 |

> **TODO**：接口 URL 与参数在网络恢复后需对照 Binaryify 仓库源码核实。本脚本先写骨架，参数用占位。

### 4.3 反爬策略

- 单 IP 每分钟 ≤ 30 次请求
- 请求间 sleep 2-5 秒随机
- User-Agent 设为 Chrome 桌面端
- 失败重试 3 次（指数退避）
- 整个 5 年榜单一轮大约 30 分钟可跑完

### 4.4 代码骨架（关键函数）

```python
# fetch_weekly_top100.py 骨架

def fetch_toplist(chart_id: int) -> list[dict]:
    """请求单个榜单的 Top 100 原始数据"""
    # TODO: 网络恢复后接入真实接口
    raise NotImplementedError

def fetch_song_detail(song_ids: list[int]) -> list[dict]:
    """批量获取歌曲元数据"""
    # TODO
    raise NotImplementedError

def iso_week_label(d: date) -> str:
    """2020-01-01 → '2020-W01'"""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"

def main(start: str, end: str, top: int, out_dir: Path):
    """主入口：扫描 [start, end] 之间所有 ISO 周"""
    # TODO
    raise NotImplementedError
```

---

## 5. Step 2：下载 .ncm（download_ncm.py，待写）

- 输入：`data/songs_catalog.json`
- 调 `GET /song/url?id={id}&br=320000`，拿下载 URL
- 输出：`data/ncm/{song_id}.ncm`
- 跳过已存在的文件
- 失败重试 3 次

---

## 6. Step 3：本地 ncm → mp3 转换（手动）

- **为什么手动**：你的工具 [Ncm转mp3拖一拖.exe](Ncm转mp3拖一拖.exe) 是 GUI 拖拽式，不接受命令行参数，无法被脚本自动调用
- **怎么手动**：每次把 `data/ncm/` 里的 .ncm 全部拖到 .exe 上，让它输出到 `data/mp3/`
- **未来自动化选项**：写一个 .NET / Python 调用 [ncmdump](https://github.com/anonymous5l/ncmdump) 或类似开源 CLI 工具替代 GUI（如果时间允许）

---

## 7. Step 4：mp3 → 向量（embed_audio.py，待写）

### 7.1 候选模型对比

| 模型 | 维度 | 大小 | 依赖 | 推荐度 |
| --- | --- | --- | --- | --- |
| Jukemir | 4800 | ~1 GB (Jukebox weights) | PyTorch + Jukebox | ⭐⭐⭐⭐⭐ |
| MusicNN | 128 | ~50 MB | TensorFlow / ONNX | ⭐⭐⭐⭐ |
| CLAP | 512 | ~400 MB | PyTorch + laion-clap | ⭐⭐⭐⭐ |

**推荐组合：Jukemir 主 + librosa 传统特征辅。** 网络恢复后跑一次 30 分钟验证。

### 7.2 产出

`data/embeddings/song_vectors.csv`（song_id × 4800 维浮点数）。

4800 维太大，**进 R 之前要先 PCA 降维**（保留解释方差 > 95% 的主成分，通常 50-100 维就够）。这一步在 R 里做更自然。

---

## 8. Step 5：清理（手动）

抽完向量后，`rm -rf data/ncm data/mp3`（或 Windows 资源管理器删掉）。**不要让 mp3 长期存在**。

---

## 9. 分析层（R）

### 9.1 笔记本结构（建议）

```
analysis/
├── 01_eda.Rmd              # 数据读入 + 描述统计 + 基础可视化
├── 02_pca_umap.Rmd         # 降维 + 2D "音乐地图"
├── 03_clustering.Rmd       # K-means / 层次聚类
├── 04_temporal.Rmd         # 时序分析（年度质心漂移）
└── 05_final_report.Rmd     # 综合报告（提交版本）
```

### 9.2 关键问题 → 对应分析

| 想知道 | 用什么方法 |
| --- | --- |
| "年度最平均歌" | 每年的向量均值 → 找最近邻 |
| "年度最特别歌" | 每首歌到年度均值的距离排名 |
| "听歌品味地图" | t-SNE / UMAP 降维到 2D |
| "流派自动归类" | K-means / 层次聚类 |
| "十年主轴漂移" | PCA 主成分 → 时间序列 |
| "哪些维度变化最大" | 每年方差最大的几个 PCA 维度的载荷分析 |

---

## 10. 时间线

### 10.1 整体节奏

| 周次 | 任务 | 负责 | 状态 |
| --- | --- | --- | --- |
| W1 | 项目初始化 + 提案 | 两人共同 | ✅ 进行中 |
| W1 末 | 验证 mp3 → embedding 跑通（30 分钟 spike） | 待定 | ⏳ 待网络 |
| W2 | 网易云榜单爬取脚本（Step 1） | 待定 | ⏳ 待网络 |
| W3 | Step 1 跑完，拿到所有榜单 JSON | 待定 | — |
| W3-W4 | Step 2-3：下载 + 转 mp3（手动） | 待定 | — |
| W4 | Step 4：mp3 → 向量（批量） | 待定 | — |
| W5 | R 端 EDA + 降维 | 待定 | — |
| W6 | R 端聚类 + 时序分析 | 待定 | — |
| W7 | Proposal 撰写（**deadline: 9/28-9/30**） | 两人共同 | — |
| W8 | 报告 + 幻灯片初稿 | 两人共同 | — |
| W9 | Buffer + 排练 presentation | 两人共同 | — |

### 10.2 风险节点

- **9/28-9/30 Proposal 截止**：必须 W7 之前出初步结论，否则赶不上
- **音频嵌入 spike（W1 末）**：如果跑不通，整个项目崩盘，立即切换到备选（librosa 传统特征 + Spotify 元数据替代）
- **反爬封 IP**：Step 1 一次性跑 260 次，运气不好可能中途被封。**对策**：脚本支持断点续跑

---

## 11. 风险 & 应对

| 风险 | 概率 | 应对 |
| --- | --- | --- |
| Jukemir / MusicNN 在 Windows 跑不起来 | 中 | 换 librosa + Spotify 元数据 |
| 网易云 API 接口变更 | 中 | 写脚本时抓原始 JSON 留底，反爬变了可以离线重跑 |
| 反爬封禁我们 IP | 低 | 限速 + 重试 + 断点续跑 |
| mp3 下载不到（有版权歌曲下架） | 中 | 跳过 + 标记 unavailable，最终向量化时排除 |
| 翻唱 / 版本归一搞不定 | 中 | 用最简单规则（出现频次最高的版本），R 端再清洗 |
| mp3 → 向量耗时过长（5 万首歌 × 5 秒/首 ≈ 70 小时） | 中 | 跑批处理脚本，留夜里跑；并发加速 |
| 法律 / 合规 | 低-中 | 仅本地用 + 不分发，论文不公开 mp3，只公开向量 |

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
| 把向量 + 元数据公开 | ✅ 可以 |

**重要**：所有 mp3 / ncm 用完即删。仓库里只允许出现 `song_vectors.csv`（数值矩阵）和 `weekly_top100/*.json`（榜单元数据）。

---

## 13. 待办 & 责任人

### 13.1 立即可做（不需要网络）

- [x] 初始化仓库
- [x] 写 README
- [x] 写 DESIGN（本文件）
- [ ] 写 fetch_weekly_top100.py 骨架（带 TODO）
- [ ] 更新 .gitignore（排除 ncm / mp3 / 缓存）

### 13.2 需要网络恢复后才能做

- [ ] 验证 Jukemir spike（30 分钟）
- [ ] 接入真实网易云 API，写完 fetch_weekly_top100.py
- [ ] 决定最终 embedding 模型
- [ ] 第一次 commit + push

### 13.3 长期 TODO（粗粒度）

- [ ] Step 2：download_ncm.py
- [ ] Step 4：embed_audio.py
- [ ] analysis/01_eda.Rmd ...
- [ ] 论文初稿
- [ ] Slides

---

## 14. 角色分工（待你和搭档确认）

建议分工（**待讨论**）：

| 任务 | 建议主负责 |
| --- | --- |
| 数据流水线（Step 1-4） | 偏 Python 工程的一方 |
| 分析 + 报告（Step 5+） | 偏 R / 统计的一方 |
| Proposal 撰写 | 共同 |
| Presentation 排练 | 共同 |

**关键原则**：双方都要理解每一行代码（Lec01 AI 政策）。

---

## 15. 变更记录

| 日期 | 修改 |
| --- | --- |
| 2026-09-07 | 初版 |