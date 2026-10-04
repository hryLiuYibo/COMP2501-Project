# Project Proposal — 草稿

> 用途：Moodle Quiz 提交（Sep 28 → Oct 3, 11:59 pm）
> 状态：草稿 v0.1，**请检查后自己填到 Moodle**
> 老师说"每行都要能讲清"，所以草稿里所有数字 / 措辞都需要你自己核一遍

---

## Q1. Tentative topic of your presentation

> **建议 100 字以内**

**How has Chinese music taste drifted on NetEase Cloud Music over 2020–2025? A five-year audio-feature space analysis of the weekly hot-song chart.**

中文版本（参考，不是必交）：基于网易云热歌榜的 5 年音频特征漂移分析

---

## Q2. One to two data science questions you are going to answer

> **1–2 个问题**

**Q1（主问题）**: 在 2020–2025 这五年里，国内热歌榜歌曲的音频特征"重心"是如何随时间漂移的？我们能不能在低维嵌入上量化并可视化这条迁移路径？

**Q2（副问题）**: 每一年热歌榜上"最特别的歌"（即距离当年均值最远的那首歌），它的"特别"在 5 年里发生了什么变化？也就是说，离群点的音频特征是否在往某个方向走？

---

## Q3. Project description (within 300 words)

> **≤ 300 字**，下面是 ~290 字版本

This project analyses how Chinese music listeners' tastes have changed on NetEase Cloud Music over the past five years (2020–2025) using its weekly hot-song chart (热歌榜, top 100 per snapshot, ≈260 weekly snapshots).

The pipeline is entirely in R: we pull each week's toplist by parsing the SSR-embedded JSON inside the page (via `httr` + `rvest` + `jsonlite`), then for every unique song download the corresponding `.ncm`, decrypt it to `.mp3` locally using the `ncmdump` CLI, and extract a 30-dimensional classical-MIR feature vector (13 MFCCs via `tuneR::melfcc`, 3 spectral descriptors, 12-bin chroma, tempo, ZCR) from the first 60 seconds of audio. `.ncm` and `.mp3` files are deleted immediately after feature extraction; nothing is redistributed.

We then ask: (i) where does the centroid of the yearly feature cloud sit in PCA / UMAP space, and how does it move year over year; (ii) which songs are furthest from their year's centroid, and does the kind of "unusual-ness" change over time. The analysis layer (R Markdown) covers EDA, PCA, UMAP, K-means clustering, and a temporal drift panel.

The project is born from curiosity (it was inspired by a now-deleted data-visualisation video about music-taste drift), not a strong real-world need. We expect to recover a small, interpretable drift signal in MFCC / chroma space, plus an evolving set of outlier songs; the value of the project is methodological and pedagogical, not commercial.

(中文要点：5 年 260 个周榜快照；纯 R；30 维手工特征；核心是 PCA / UMAP 看漂移 + 离群歌变化；动机是个人好奇，不是商业价值。)

---

## Q4. Why are the questions important? (and the related sub-prompts)

> Moodle 上原题是 4 个小问合并：**"Why important? / 难度？/ 现有工作？/ 数据可得？"**
> 老师期望看到的是简短的反思，不是长篇。下面分 4 个子问回答：

### Why important?

重要性**有限**。这是一个出于个人好奇心的小型数据练习，没有直接的商业或政策落地需求。**对方法论有意义**：它示范了"用低维音频特征 + 公开榜单 + 经典降维"完成一次端到端时序分析的工作流，这对以后做更严肃的音乐/媒介数据项目是一个模板。从公众认知角度，**国内音乐品味的可量化研究公开成果很少**，所以哪怕只是产出几条可读结论，也对公共讨论有边际价值。

### What are the difficulties in answering the questions?

1. **历史快照不存在**：网易云不发布任何历史周榜归档，必须靠"现在反复抓取 + 用抓取日期当时间戳"重建时间序列。这意味着要赶在 9/28 之前就开始积累快照，否则回溯不完整。
2. **反爬风险**：网易云有 IP 限流和滑块验证。我们只拉页面、不调签名 API，相对安全，但仍需 2–5 秒随机间隔。
3. **音频特征 vs 流派语义**：30 维手工特征能描述"音色 / 节奏 / 音高分布"，**不能**直接刻画"流派"。我们的"品味变迁"只能在音频空间里谈，**不能直接说"华语流行 → 嘻哈"**这种语义结论。这是一个必须诚实的边界。
4. **版本归一**：同一首歌有原唱 / 翻唱 / live 多个版本。我们用"网易云给的最热门版本"作为代表，可能引入小幅噪声。
5. **数据规模 vs 维度**：30 维 vs 约 500–1000 首唯一歌，PCA / 聚类都稳；但 UMAP 在小样本上可能"看起来漂移"实际是噪声，需要做置换检验 (permutation test) 验证漂移显著。

### Are there existing works?

- **音乐品味的时序分析**：MIT Media Lab 的 "Music Lab"（Salganik 2006）是经典实验型研究；Spotify 在内部做过年度 "Music Migration" 类研究但**不公开**。
- **国内类工作**：B 站、知乎、豆瓣有音乐偏好的定性讨论，但**没有基于榜单的定量分析公开论文**。最近的是 2023 年某 B 站 UP 主做的"10 年抖音热歌可视化"（**视频已不可访问**），那个视频是这个项目最直接的灵感来源。
- **音乐推荐 / 流派分类**领域有大量公开工作（Spotify 的 Echoprint、MusicNN、Jukemir），但都是**面向推荐/分类**而非"品味变迁"。

我们能查到的国内空白是：**网易云榜单 + 时序 + 量化漂移** 这一组合没有公开学术成果。学术上发不了顶刊，但作为 COMP2501 课程项目是合理的。

### Are there data available?

- ✅ **网易云热歌榜页**（无需登录，无需签名）：已实测可访问，返回前 200 首 JSON，足够支撑项目。
- ✅ **`.ncm` 解密 CLI**：`ncmdump` (taurusxin fork) 开源、已实测在 Windows 工作。
- ✅ **音频特征提取 R 包**：`tuneR` + `seewave` 已实测可用，30 维特征可批量产出。
- ⚠️ **历史快照**：只能从现在开始抓，每周一份；做 5 年回顾就只能等 2026/2027 才能完整（2025 年部分完整可由"现在开始每周抓 + 之前手动抓取 2020–2024"补齐；后者依赖运气）。
- ⚠️ **法律边界**：`.ncm` 在本地解密 + 抽完特征立刻删除，**不上传、不分享**；只把特征 csv 入仓。已写入 DESIGN.md §12。

---

## 写作提示（自查清单）

提交前请自己核一遍：

- [ ] Q1 题目 ≤ 100 字（你 draft 是 ~120 字，可以再压一压）
- [ ] Q2 两个问题各自独立、措辞可衡量（"是否能看到漂移" / "最特别歌的特征变化"）
- [ ] Q3 ≤ 300 字（draft ~290 字）
- [ ] Q4 四小问每个都有具体内容，不要泛泛
- [ ] "B 站视频已消失" 这个细节**可加可不加** —— 如果 Moodle 有字数限制可以省

提交后：把上面 Q1–Q4 的英文 / 中文答案按 Moodle 顺序贴进去即可。

---

## 修订记录

| 日期 | 版本 | 备注 |
|---|---|---|
| 2026-09-21 | v0.1 | 初稿，等用户核 |