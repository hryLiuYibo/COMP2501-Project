# 数据状态快照（2026-09-28）

> 这份是状态记录，**不是 Proposal 草稿**。当 Excel 写好后，请核对本表再决定 Proposal 怎么改。

## 你提供的信息（口头）

- 网易云红心歌单 516 首歌
- 第一首歌大约 2022 年加入歌单
- 你现在还在用网易云

## 实际下载下来的文件（已确认）

```
C:\CloudMusic\                                40 首（mp3，非 VIP 直接下下来的）
├── *.mp3, *.lrc
└── VipSongsDownload\                          467 首（ncm，要 ncmdump 转 mp3）
    └── *.ncm, *.lrc
```

**总数**：40 + 467 = **507 个音频文件**（接近你说的 516，差 9 首可能是下架或 VIP 限制）。

按文件修改时间看，所有文件都是 **2026-09-28 14:42–14:53** 这个时间窗下的，所以**文件 mtime 不能当 first_played 用**（粒度太粗）。

## 还需要你提供的东西

### Excel/CSV 表格

按你之前说的，5 列：

| 列名 | 内容 | 例子 |
|---|---|---|
| `song_name` | 歌名 | "海阔天空" |
| `artist` | 艺人（可 `A&B&C` 多分隔）| "Beyond" |
| `song_id` | 网易云 64-bit id（数字）| 1234567 |
| `first_played` | 第一次听 / 加红心的时间 | "2022-03-15" / "2023/1/5" / NA |
| `play_count` | 听歌次数（可 NA）| 45 |

格式细节：`R/import_personal_excel.R` 已经能处理：
- 分隔符 `;` / `,` / tab 自动探测
- 日期 `YYYY-MM-DD` / `YYYY/MM/DD` / `YYYY.MM.DD` / Excel 序列日期 / `NA`
- 多艺术家拆分 `&` / `/` / `、` / `，` / `feat.`
- 缺失字段输出 JSON `null`

### 当前脚本状态

| 脚本 | 状态 |
|---|---|
| `R/fetch_weekly_top100.R` | ✅ 实测，但路线被放弃（网易云不发历史快照） |
| `R/convert_ncm_to_mp3.R` | ✅ 实测，可批量转 467 首 ncm |
| `R/build_songs_catalog.R` | ✅ 实测（按文件名建立） |
| `R/extract_audio_features.R` | ✅ 实测（3 首），可扩到 507 首 |
| `R/import_personal_excel.R` | ✅ 实测（合成数据），等你给真实 Excel |
| `R/analysis/01_eda.Rmd` | ⚠️ 骨架，需要接 `personal_history.csv` |

## 关于 Proposal 的关键事实

1. **5 年 = 2022-2026**：你最开始提到的 2020-2025 应该是口误，我之前也跟你理解错了。Proposal 写**22-2026** 还是写 **22-26** 都行，自己选。
2. **数据源不再是热歌榜**：
   - 原计划：网易云官方热歌榜 5 年周榜 260 个快照
   - 现计划：**你个人**红心歌单 516 首，按 first_played 分到 22-26 五年
3. **数据采集层已经备好**，等你的 Excel 一来就跑端到端

## 关于 PROPOSAL_draft.md 的待办

旧 draft（基于热歌榜路线）里有 4 个 section 都提到"网易云热歌榜"。**等你给 Excel 之后**，我会基于这份新数据状态重写 draft。你现在不需要看 / 改旧 draft。

---

## 现在你能做的事

1. **写 Excel**（不急）—— 5 列格式如上
3. **决定 Proposal 题目措辞**：22-2026 vs 22-26 vs 2022-2026 都行，看哪个简洁

## 我现在能做但被你说"先不动"的事

- ❌ 把 467 个 ncm 转 mp3（放到哪里你说"先不动"）
- ❌ 抽 507 首歌的特征
- ❌ 重写 PROPOSAL_draft.md
- ❌ 重写 README.md / DESIGN.md / TODO.md 的"热歌榜"措辞

## 等你 Excel 来之后的计划

1. 跑 `R/import_personal_excel.R` 产 catalog
2. （如果 Excel 跟 mp3 文件名能 join 出来）跑 `R/extract_audio_features.R` 产特征
3. 把 `R/analysis/01_eda.Rmd` 改成读 personal_history.csv 出图
4. 重写 PROPOSAL_draft.md
5. 提交 Moodle