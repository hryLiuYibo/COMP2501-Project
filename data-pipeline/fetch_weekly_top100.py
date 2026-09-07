# -*- coding: utf-8 -*-
"""
fetch_weekly_top100.py
======================

抓取网易云音乐"热歌榜"Top 100，按周保存快照。

⚠️ 当前状态：骨架版本，核心网络逻辑还未接入真实 API。
   等网络恢复后，需要：
   1. 在本机跑 NeteaseCloudMusicApi (Node.js)，拿到 endpoint
   2. 把下面的 BASE_URL / endpoints 填好
   3. 实现 fetch_toplist() 和 fetch_song_detail()

输出结构
--------
data/raw/weekly_top100/
    2020-W01.json
    2020-W02.json
    ...
每个 JSON:
{
  "week": "2020-W01",
  "snapshot_time": "<ISO 时间>",
  "platform": "netease",
  "chart_id": <int>,
  "songs": [
    {"rank": 1, "song_id": <int>, "name": "...", "artists": ["..."], "duration_ms": <int>},
    ...
  ]
}

用法
----
$ python fetch_weekly_top100.py \
    --start 2020-W01 \
    --end   2025-W52 \
    --top   100 \
    --out   ../data/raw/weekly_top100

断点续跑
--------
已存在的 .json 文件会被跳过；删除对应文件即可重抓。
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# 配置区：网络恢复后填这些
# ---------------------------------------------------------------------------

# 跑 NeteaseCloudMusicApi (Node.js) 时它默认监听这个端口
BASE_URL = "http://localhost:3000"  # TODO: 网络恢复后确认

# 热歌榜的 chart_id,可在 /toplist 接口返回里查到
NETEASE_HOT_TOP_CHART_ID = 3778678  # 网易云"热歌榜"  # TODO: 确认

# 反爬节流（秒），随机区间
REQUEST_SLEEP_RANGE = (2.0, 5.0)

# 失败重试
MAX_RETRIES = 3
RETRY_BACKOFF = 5  # 指数退避基数（秒）

# 请求头
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fetch_weekly_top100")


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WeekLabel:
    """ISO 周标签,例如 2020-W01"""
    iso_year: int
    iso_week: int

    @classmethod
    def from_string(cls, s: str) -> "WeekLabel":
        """解析 'YYYY-Www' 格式"""
        # TODO: 加格式校验,失败抛 ValueError
        year_str, week_str = s.upper().split("-W")
        return cls(int(year_str), int(week_str))

    def __str__(self) -> str:
        return f"{self.iso_year}-W{self.iso_week:02d}"

    def to_date(self) -> date:
        """ISO 周的周一日期"""
        return date.fromisocalendar(self.iso_year, self.iso_week, 1)

    def next(self) -> "WeekLabel":
        """下一周"""
        d = self.to_date() + timedelta(days=7)
        iso = d.isocalendar()
        return WeekLabel(iso.year, iso.week)


@dataclass
class SongEntry:
    """榜单上的单首歌"""
    rank: int
    song_id: int
    name: str
    artists: list[str]
    duration_ms: int

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "song_id": self.song_id,
            "name": self.name,
            "artists": self.artists,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# 网络层
# ---------------------------------------------------------------------------

def _sleep():
    """随机反爬节流"""
    time.sleep(random.uniform(*REQUEST_SLEEP_RANGE))


def _request_with_retry(url: str, params: dict | None = None) -> dict:
    """
    带重试的 HTTP GET,返回 JSON dict。

    依赖: pip install requests
    网络恢复后,把 import 提到顶部并启用。
    """
    # TODO: 网络恢复后启用
    # import requests
    # headers = {"User-Agent": USER_AGENT}
    # last_err = None
    # for attempt in range(1, MAX_RETRIES + 1):
    #     try:
    #         r = requests.get(url, params=params, headers=headers, timeout=15)
    #         r.raise_for_status()
    #         data = r.json()
    #         if data.get("code") != 200:
    #             raise RuntimeError(f"API returned code={data.get('code')}: {data}")
    #         return data
    #     except Exception as e:
    #         last_err = e
    #         backoff = RETRY_BACKOFF * (2 ** (attempt - 1))
    #         log.warning("请求失败 (%d/%d): %s, %.1fs 后重试", attempt, MAX_RETRIES, e, backoff)
    #         time.sleep(backoff)
    # raise RuntimeError(f"重试 {MAX_RETRIES} 次后仍失败: {last_err}")
    raise NotImplementedError("_request_with_retry 尚未接入真实 API")


def fetch_toplist(chart_id: int, top: int = 100) -> list[dict]:
    """
    请求单个榜单的 Top 100 原始数据。

    推荐接口: GET {BASE_URL}/toplist/detail?id={chart_id}
    返回示例:
      {
        "code": 200,
        "list": {
          "id": 3778678,
          "name": "热歌榜",
          "tracks": [
            {"id": 1345863568, "name": "芒种", "ar": [{"name": "音阙诗听"}], "dt": 235000},
            ...
          ]
        }
      }

    返回: list[dict],每项含 song_id / name / artists / duration_ms
    """
    # TODO: 网络恢复后接入
    # url = f"{BASE_URL}/toplist/detail"
    # data = _request_with_retry(url, params={"id": chart_id})
    # tracks = data["list"]["tracks"][:top]
    # return [
    #     {
    #         "song_id": t["id"],
    #         "name": t["name"],
    #         "artists": [a["name"] for a in t.get("ar", [])],
    #         "duration_ms": t.get("dt", 0),
    #     }
    #     for t in tracks
    # ]
    raise NotImplementedError("fetch_toplist 尚未接入真实 API")


def fetch_song_detail(song_ids: list[int]) -> list[dict]:
    """
    批量获取歌曲元数据 (用作交叉验证 / 补字段)。

    推荐接口: GET {BASE_URL}/song/detail?ids={csv}
    """
    # TODO: 网络恢复后接入
    raise NotImplementedError("fetch_song_detail 尚未接入真实 API")


# ---------------------------------------------------------------------------
# 落盘逻辑
# ---------------------------------------------------------------------------

def save_snapshot(week: WeekLabel, chart_id: int, songs: list[SongEntry], out_dir: Path) -> Path:
    """保存单周榜单 JSON"""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{week}.json"

    if out_path.exists():
        log.info("已存在,跳过: %s", out_path)
        return out_path

    payload = {
        "week": str(week),
        "snapshot_time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": "netease",
        "chart_id": chart_id,
        "songs": [s.to_dict() for s in songs],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("已写入: %s (%d 首歌)", out_path, len(songs))
    return out_path


def iter_weeks(start: WeekLabel, end: WeekLabel) -> Iterable[WeekLabel]:
    """从 start 到 end (含)按周迭代"""
    cur = start
    while str(cur) <= str(end):
        yield cur
        cur = cur.next()
        # 防御性终止,避免死循环
        if cur.iso_year > end.iso_year + 1:
            break


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="抓取网易云热歌榜 Top 100,按周保存为 JSON"
    )
    parser.add_argument("--start", required=True, help="起始周,例如 2020-W01")
    parser.add_argument("--end", required=True, help="结束周,例如 2025-W52")
    parser.add_argument("--top", type=int, default=100, help="每个榜单取前 N 首")
    parser.add_argument("--chart-id", type=int, default=NETEASE_HOT_TOP_CHART_ID,
                        help="榜单 ID (默认 3778678 = 热歌榜)")
    parser.add_argument("--out", type=Path, required=True, help="输出目录")
    args = parser.parse_args(argv)

    start_week = WeekLabel.from_string(args.start)
    end_week = WeekLabel.from_string(args.end)

    if str(start_week) > str(end_week):
        log.error("--start (%s) 不能晚于 --end (%s)", start_week, end_week)
        return 2

    log.info("抓取范围: %s → %s, 榜单 ID=%d, 输出到 %s",
             start_week, end_week, args.chart_id, args.out)

    total_weeks = 0
    total_songs = 0
    for week in iter_weeks(start_week, end_week):
        try:
            raw = fetch_toplist(args.chart_id, top=args.top)
            songs = [
                SongEntry(
                    rank=i + 1,
                    song_id=int(item["song_id"]),
                    name=item["name"],
                    artists=list(item.get("artists", [])),
                    duration_ms=int(item.get("duration_ms", 0)),
                )
                for i, item in enumerate(raw)
            ]
            save_snapshot(week, args.chart_id, songs, args.out)
            total_weeks += 1
            total_songs += len(songs)
        except NotImplementedError:
            log.error("fetch_toplist 尚未实现,请先接入真实 API (见函数体内 TODO)")
            return 1
        except Exception as e:
            log.exception("周 %s 抓取失败: %s", week, e)
            # 继续下一周,不整体中断
        finally:
            _sleep()

    log.info("完成。共处理 %d 周,累计 %d 条榜单记录", total_weeks, total_songs)
    return 0


if __name__ == "__main__":
    sys.exit(main())