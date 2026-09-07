# Data Pipeline

数据采集与预处理流水线（Python）。分析层在 `analysis/`，R 负责。

## 当前脚本

| 脚本 | 作用 | 状态 |
| --- | --- | --- |
| `fetch_weekly_top100.py` | 抓网易云热歌榜 Top 100，按周保存 JSON | 骨架已写，待接入真实 API |

## 即将加入

- `download_ncm.py` — 按 song_id 批量下载 .ncm
- `embed_audio.py` — mp3 → 特征向量

## 安装依赖

```bash
pip install requests
# 后续音频处理：pip install librosa torch jukemir
```

## 启动网易云 API 后端（待网络恢复后补充）

依赖 [NeteaseCloudMusicApi](https://github.com/Binaryify/NeteaseCloudMusicApi) Node.js 项目作为后端代理。安装与启动步骤在网络恢复后补充。

## 用法示例

```bash
python fetch_weekly_top100.py \
    --start 2020-W01 \
    --end   2025-W52 \
    --top   100 \
    --out   ../data/raw/weekly_top100
```

- 已存在的快照会被跳过（断点续跑）
- 失败不中断整轮，按周记录

## 数据落盘约定

```
data/raw/weekly_top100/
    2020-W01.json
    2020-W02.json
    ...
```

每个 JSON 的 schema 见 `../DESIGN.md` 第 3 节。