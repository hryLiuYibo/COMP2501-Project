# 合并计划 — 与同伴工作合并（2026-10-04）

> 这份计划讲**做什么、按什么顺序、怎么分工**。
> 不写技术细节，技术细节等行动时再展开。

---

## 0. 一句话总结

**以同伴 QQ 跨平台分析为报告主体，你贡献 1 节："个人品味偏离主流中心"——但你贡献的形式是一个可重用的小工具（Rmd 报告生成器），对任何用户输入的 csv 都能输出"自己距离主流 QQ 137K 中心多远"的报告**。

---

## 1. 现状盘点

### 同伴 `sound_of_decade/`

| 项 | 内容 |
|---|---|
| 仓库位置 | `C:\Users\Surface\Desktop\Resources-SHsem\COMP2501\Proj\sound_of_decade\sound_of_decade\` |
| 数据 | QQ 音乐 7 榜单（topId 26/28/5/58/57/65/60）× 2018W30–2024W52（7 年），**~137,000 行**，29,500 唯一歌 |
| 跨平台 | QQ + 网易云 / Apple Music CN / Apple Music US **当前快照**（不是历史） |
| 核心结论 | 3 个变更点 2019/2020/2022 (p<0.001)；Hot↔Rap 反相关 -0.89；Hot↔Douyin Hit 反相关 -0.76 |
| 分析脚本 | 12 个 R 脚本（00_smoke + 01_clean … 17_cross_region_patterns）|
| 报告 | `R/report.html` 已 knit（1.77 MB）+ `R/report.Rmd`（18 KB）|
| 包管理 | `renv.lock`（69 个 R 包锁版本）|
| 文档 | `docs/`（PROJECT_STATUS、DATA_DICTIONARY、CROSS_PLATFORM_NOTES、FINDINGS_INTERPRETATION、data_acquisition_methodology）|
| **audio embedding** | ❌ **out of scope per user request**（README + PROJECT_STATUS 多处标） |
| 走 Python | QQ `u.y.qq.com` 接口；3 个操作 33 行；CSV 入仓后**纯 R 即可复现** |

### 你 `COMP2501-Project/`

| 项 | 内容 |
|---|---|
| 仓库位置 | `C:\Users\Surface\Desktop\Resources-SHsem\COMP2501\Proj\COMP2501-Project` |
| 已写脚本 | `R/fetch_weekly_top100.R`（网易云单榜）<br>`R/convert_ncm_to_mp3.R`<br>`R/build_songs_catalog.R`<br>`R/extract_audio.R`（30 维手工特征）<br>`R/import_personal_excel.R`（CSV 接收）<br>`R/analysis/01_eda.Rmd` 等 3 个 Rmd 骨架 |
| 数据 | 1 周榜单快照 (2026-W39)；3 首 mp3 demo；40 mp3 + 467 ncm = 507 个 C:\CloudMusic |

### 你之前的工作**几乎全部要丢弃**

| 你的脚本 | 新路线下的角色 |
|---|---|
| `R/fetch_weekly_top100.R` | ❌ 不再需要（QQ 是主体；网易云单榜失效） |
| `R/convert_ncm_to_mp3.R` | ❌ 不再需要（工具不抽 mp3 特征） |
| `R/build_songs_catalog.R` | ❌ 不再需要（个人数据用 import_personal_excel 路径） |
| `R/extract_audio.R` | ❌ 不再需要 |
| `R/import_personal_excel.R` | ❌ 不再需要（工具不绑死你的 Excel；CSV 解析逻辑可挪进工具） |
| `R/analysis/*.Rmd` | 🔁 重写为"个人偏离"小节 Rmd |

---

## 2. 合并路线（已拍板）

### 2.1 报告结构

```
sound_of_decade/
├── R/00_smoke.R                       烟测
├── R/01_clean.R → 02_yearly_summary.R → 03_umap.R → 04_special_songs.R
│   → 05_changepoint.R → 06_toplist_compare.R → 07_version_normalize.R
│   → 08_topid_overview.R → 09_genre_drift.R → 14_lof_outliers.R
│   → 15_covid_qq_features.R → 17_cross_region_patterns.R        (同伴)
├── R/18_personal_offset.R              ★ 你新增：通用"个人偏离"小工具
├── R/19_personal_offset_examples.Rmd   ★ 你新增：Rmd 报告生成器
├── R/report.Rmd                        ★ 加一节 "Personal Offset"，引到上面的 Rmd
├── R/report.html                       重新 knit
├── docs/...
└── pipeline/qq_official/...            (Python, 只动数据采集层)
```

### 2.2 工具定位**（这次关键）**

**`R/19_personal_offset_examples.Rmd` 是一个独立的 Rmd 报告生成器**：

- 输入：**任意 CSV**（用户的红心 / 听歌记录 / 自定义列表）
- 算法：自动切换"基准数据集"——若 csv 里有 QQ song_id，用 QQ 137K 中心；若只有网易云 song_id，用网易云当前快照；若只是文本歌名，fuzzy match
- 输出：HTML 报告，包含：
  1. **类别分布偏离**：用户 7 榜单 / 流派覆盖 vs 主流 QQ 137K 类别分布（卡方检验 / KL 散度）
  2. **特征空间偏离**：把用户的 chart-history 元信息（weeks_total, peak_rank, top_ids_present, genres）投到 QQ 137K 5 维中心空间，算 Mahalanobis 距离或 z-score
- 这是**工具**，不绑死任何具体数据；你只是开发者，报告里演示 1-2 个例子

### 2.3 时间窗口

- 同伴：**2018W30–2024W52**（QQ 限定）
- 工具：**无关时间**——输入的 csv 自带时间戳，工具用 csv 自带的字段
- PPT 报告：以同伴的 QQ 7 榜单 7 年变迁为主，你的工具作为"补数据 / 副产品"展示

### 2.4 关于"audio embedding"

继续**不做**。工具走 chart-history 路径（QQ 137K 已有的5 维特征），不走 30 维音频特征。理由：QQ per-song endpoint 已锁（`code=500003`），强行抽 mp3 特征会让工具受限于用户的本地 mp3 文件。

---

## 3. 行动清单（按优先级）

### Phase 1：写"个人偏离"小工具 ★ 你的核心交付

| 任务 | 谁 | 备注 |
|---|---|---|
| (P1-1) 写 `R/18_personal_offset.R` | 我 | 核心函数：接收用户 csv + QQ 137K 中心，输出两个偏离指标 |
| (P1-2) 写 `R/19_personal_offset_examples.Rmd` | 我 | 把函数包进 Rmd，给出 1-2 个示例输入 |
| (P1-3) 智能基准切换 | 我 | csv 有 QQ id → 用 QQ；有网易 id → 用网易云当前快照；只有歌名 → fuzzy |
| (P1-4) 工具接入同伴 report.Rmd | 我 | 在 `R/report.Rmd` 加一节 "8. Personal Offset Tool" |

### Phase 2：示例数据（**仍需准备**）

| 任务 | 谁 | 备注 |
|---|---|---|
| (P2-1) 你手写 1-2 个示例 csv | 你 | 1 个是你自己的 516 首歌（你说仍要准备 1-2 个示例）|
| (P2-2) 跑工具得到示例输出 | 我 | 演示 Rmd 怎么用 |
| (P2-3) 把示例嵌入 PPT | 我 | "your personal pop" 演示 |

### Phase 3：合进同伴的报告

| 任务 | 谁 | 备注 |
|---|---|---|
| (P3-1) 在 `R/report.Rmd` 末尾加一节 "8. Personal Offset Tool" | 我 | 引到 R/18 + 嵌 1 个示例 |
| (P3-2) 重新 knit `R/report.html` | 我 | |
| (P3-3) `PROPOSAL.md`（两份合成一份）| 共同 | 用他的 PROPOSAL_QQ_DATA_SECTION.md 作第 4-5 节 |

### Phase 4：交付物清单

- [ ] `R/18_personal_offset.R`（你新增核心脚本）
- [ ] `R/19_personal_offset_examples.Rmd`（你新增 Rmd 生成器）
- [ ] `examples/example_user.csv`（1-2 个示例）
- [ ] `R/report.Rmd` 加 "8. Personal Offset Tool" 一节
- [ ] `R/report.html` 重新 knit
- [ ] `PROPOSAL.md`（合并版）
- [ ] `PROPOSAL_CLEAN.txt`（合并版）
- [ ] PPT slides

---

## 4. 风险与决策点

| 风险 | 后果 | 缓解 |
|---|---|---|
| CSV 输入格式五花八门 | 工具难以解析 | Rmd 里给出"输入 csv 模板"，强制 schema |
| 用户歌名与 QQ 137K 库 fuzzy match 命中率低 | 类别偏离算不准 | 报告里同时给出"matched / unmatched counts"，未匹配的标 "unknown" 不算 |
| QQ vs 网易云 song_id 仍不通用 | 切换基准时需手动对齐 | 工具运行时让用户**指定** csv 里的 song_id 是哪个平台 |
| 同伴工程是 Mac 路径（`/Users/johnny/`） | Windows 上不能直接 `Rscript R/01_clean.R` | ROOT 用 `normalizePath(".")` 取当前目录；迁到 Windows 后改路径即可 |

---

## 5. 顺序与阻塞

```
P1-1 P1-3 写              ★ 我先做
    ↓
P2-1 你写 1–2 个示例 csv
    ↓
P2-2 跑工具
    ↓
P3-1 加进 report.Rmd → P3-2 knit → P3-3 Proposal

无关键阻塞：工具不依赖你具体 csv，可先行。
```

---

## 6. 不要做的事

- ❌ 把你的 `R/fetch_weekly_top100.R` 改去抓 QQ 榜单
- ❌ 试图把 QQ 的 Python 脚本重写为 R（重复劳动）
- ❌ 推翻同伴已有的变更点分析
- ❌ 把工具绑死你个人的 516 首歌（必须泛化）
- ❌ 抽 mp3 30 维特征（已 out of scope）
- ❌ 改写你之前的 PROPOSAL_draft.md / DESIGN.md（路线已变，等合并版 Proposal 一起重写）

---

## 7. 时间预估

| 任务 | 估计 |
|---|---|
| P1-1 写 `R/18_personal_offset.R` | 我 3-4 小时 |
| P1-2 写 Rmd 生成器 | 我 1-2 小时 |
| P1-3 智能基准切换 | 我 1 小时 |
| P1-4 接入 report.Rmd | 我 30 分钟 |
| P3-1 P3-2 P3-3 整合 | 我 1 小时 |
| **总：我的工作量约 7-9 小时**（你那边：准备 1-2 个示例 csv，约 30 分钟）| |

---

## 8. 仍待你确认的（更新版）

| 决策点 | 选项 |
|---|---|
| (A) **示例 csv 数量** | 1) 1 个示例（最小）<br>2) 2 个示例（不同分布：你自己 + 假设的"高一致人群"）|
| (B) **基准切换策略** | 1) 让用户在 csv 头部 metadata 标注 song_id 平台<br>2) 工具自动探查（看 song_id 前缀 / 长度）<br>3) 工具只支持 QQ 137K 中心，其他平台报 "out of scope"|
| (C) **报告提交位置** | 1) 留在同伴的 `sound_of_decade/` 仓库<br>2) 迁到你现在的 `COMP2501-Project/`<br>3) 新建第三个仓库 |
| (D) **你的示例 csv 是哪一首** | 1) 你 516 首里的抽样<br>2) 你 40 首 mp3 里挑<br>3) 你从 QQ 7 榜单里挑（如 1 首热歌 + 1 首说唱）|

**(A) 和 (B) 可以暂时不定，我先按"2 个示例 + 头标"实现**。

---

## 9. 修订记录

| 日期 | 版本 | 备注 |
|---|---|---|
| 2026-10-04 | v0.1 | 初稿 |
| 2026-10-04 | v0.2 | 用户确认：报告以同伴为主；你的贡献 = 通用工具；两个算法都做；仍准备 1-2 个示例 |