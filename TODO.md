# TODO — 下一步要做什么

> 这份清单按"做完一项划掉一项"维护。任何想加进来的事，先写在这里再开干。

## 0. 当前状态（2026-09-21）

| 模块 | 状态 | 备注 |
| --- | --- | --- |
| 抓榜单元数据（`R/fetch_weekly_top100.R`） | ✅ 实测 100 首 | 一次只能抓"今天"的榜 |
| ncm → mp3（`R/convert_ncm_to_mp3.R` + ncmdump.exe） | ✅ 实测 3 首 | ncmdump.exe 已下到 `~/tools/`（不放仓） |
| catalog 索引（`R/build_songs_catalog.R`） | ✅ 实测 3 条 | 支持"艺人 - 标题"自动拆分 |
| 抽特征（`R/extract_audio_features.R`） | ✅ 实测 3 × 30 维 | MFCC + 自实现 spectral/chroma + tempo/zcr |
| 分析层（`R/analysis/01_eda.Rmd` 等） | ⚠️ 仅骨架 | 占位代码，没有接真实数据 |
| 5 年榜单快照 | ❌ 只有 2026-W39 一周 | 没批量抓 |

---

## P0 — 离 Proposal 截止（9/28–9/30）必须做完的

> 课程截止日期：2026-09-28 ~ 2026-09-30 11:59pm（参考 README）。
> 倒推：**最晚 9/27** 必须把 Proposal 写完。

- [ ] **抓 5 年榜单快照**（约 260 个 .json）
  - 写一个 `R/fetch_range.R` 脚本，调 `fetch_weekly_top100.R` 的内部函数循环跑
  - 或者直接在 R 里写个 `for (week in seq(start, end, by="week"))` 套 `fetch_toplist()`
  - 限速保持 2-5s 随机（防止封 IP），全程约 17-30 分钟
  - 验证：最后一周快照应该是真实的最近榜（与浏览器对比）

- [ ] **把 `R/analysis/01_eda.Rmd` 接上真实数据**
  - 读 `data/raw/weekly_top100/*.json`，用 `purrr::map_dfr` 合成一张 `all_snapshots` 表
  - 出三张图：
    1. 每年**新增歌**数量（deduplicated）
    2. **Top 20 最持久**歌曲（在榜周数）
    3. **排名熵**逐年变化（流派多样性的代理）
  - 这三张图就是 Proposal 里"故事"的核心

- [ ] **跑 `R/analysis/02_dimension_reduction.Rmd` 跑通**（哪怕只 5 年均值漂移也行）
  - PCA 跑 `data/embeddings/song_features.csv`
  - 至少画出"PC1 vs PC2，颜色 = year" 的散点图

- [ ] **写 Proposal**（**最重要**）
  - 1-2 页 PDF，回答：研究问题、数据、方法、初步发现、风险
  - 可以参考 `Proj_Proposal_Firstidea.md` 改写

---

## P1 — 数据规模扩展

- [ ] **批量下载 mp3**
  - 当前只有 3 首测试，5 年榜单约 200-500 唯一歌
  - 写一个简单的 `R/download_ncm.R`（或者直接用 pyncm 写个小 Python helper，**不用 R 写加密**）
  - **法律红线**：仅本地、仅研究用、不上传、不分享

- [ ] **把 mp3 来源统一到 song_id 命名**
  - 现在的 catalog key 是 "艺人 - 标题"，无法 join 到榜单
  - 需要 NetEase API 反查每首歌的 song_id（写一个 `R/lookup_song_ids.R`）
  - 或者：写一个 `R/build_songs_catalog.R --from-snapshots` 模式，把 snap 的 song_id 反向填进 catalog

---

## P2 — 分析层深化（presentation 之前）

- [ ] **PCA 主轴时间序列**
  - 把"年度质心"画在 PCA 空间里，看 5 年的漂移方向
  - 这就是 "taste drift" 的可视化核心

- [ ] **流派自动归类**
  - 用 K-means（k=8 或 10）聚类 30 维特征
  - 每个 cluster 找出代表性曲目，听感校准 cluster 名称

- [ ] **艺人维度**
  - 把每首歌的 artist join 进特征表
  - 谁最持久？谁的歌最"中心"？谁最"极端"？

---

## P3 — 工程化 / 长期

- [ ] **抽特征的批处理加速**
  - 当前 3 首约 14 秒，500 首约 30-40 分钟
  - 可以用 `parallel::mclapply` 跑多核
  - 但要先确认每首歌 truncate 到 60s 后还稳

- [ ] **错误处理增强**
  - 现在 30 维里某些列（如 tempo）如果是 NA，PCA 会报错
  - 加 `recipes::step_impute_*` 或写一个简单的 NA 填充

- [ ] **R Markdown 报告润色**
  - 现在 `01_eda.Rmd` 等只有骨架
  - Proposal 通过后，把所有代码 + 文字填进去，knit 出 HTML

- [ ] **Slides**
  - 用 xaringan 包做 slides（HTML 格式，可交互）
  - 10-20 min presentation

---

## 风险 / 备选

- [ ] **如果反爬彻底封了**：考虑用 last.fm 历史数据替代
- [ ] **如果 5 年抓不全**：把时间范围缩到 2022-2025（最近 3 年）
- [ ] **如果 30 维特征不够有 story**：换用 `audio.whisper` 或自训练的 word2vec on chroma 序列

---

## 协作约定（不要忘了）

- 所有内部文档 / commit 注释：中文
- README（公开版） + Rmd 报告 + commit message：英文（已实施）
- AI 政策：LLM 辅助可以，每行代码自己都能讲清
- 每次大改先 commit，写清楚做了什么、为什么
- 长期 commit 前先 `git status` 看一眼

> 最后更新：2026-09-21 21:09
