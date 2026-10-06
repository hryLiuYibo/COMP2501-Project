#!/usr/bin/env python3
"""QQ Music weekly toplist history collector.

We hit the public endpoint `https://u.y.qq.com/cgi-bin/musicu.fcg`
which is what the QQ Music web client itself uses; no login required,
no anti-bot headers, no rate limit issues observed.

For topId=26 (热歌榜, Hot Songs), the period parameter accepts:
  - YYYY-MM-DD for >= 2022-01-01
  - YYYY_WNN   for 2018-30 .. 2024-52 (weekly issue number)

For topId=28 (网络歌曲榜, Online Songs), the historical coverage
also spans 2018-30 .. 2024-52.

Strategy
--------
1. Probe each (year, week) and only keep issues where the server
   honours the period (i.e. period_used == period_requested).
2. Write one CSV per (topId, period).
3. Aggregate into a long-format CSV at the project level.

Output columns:
  top_id, top_title, period, rank, song_id, song_mid, song_title,
  singer_name, singer_mid, album_mid, cover, song_type, fetched_at
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw" / "qq"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_RAW.mkdir(parents=True, exist_ok=True)
DATA_INTERIM.mkdir(parents=True, exist_ok=True)

URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
HDR = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Referer": "https://y.qq.com/",
    "Content-Type": "application/json; charset=utf-8",
}

def _post(payload: dict, retries: int = 3):
    for i in range(retries):
        try:
            r = requests.post(URL, headers=HDR, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  retry {i+1}/{retries}: {e}", file=sys.stderr)
            time.sleep(1.5 * (i + 1))
    return None

def fetch(top_id: int, period: str, num: int = 100):
    payload = {
        "comm": {"ct": 24, "cv": 0},
        "detail": {
            "module": "musicToplist.ToplistInfoServer",
            "method": "GetDetail",
            "param": {
                "topId": top_id,
                "offset": 0,
                "num": num,
                "period": period,
            },
        },
    }
    d = _post(payload)
    if not d:
        return None
    if d.get("detail", {}).get("code") not in (200, 0, "200"):
        return None
    info = d["detail"].get("data", {}).get("data", {}) or {}
    used_period = info.get("period")
    return info, used_period

def period_is_valid(used: str | None, requested: str) -> bool:
    """Server honour means period_used matches period requested."""
    return used is not None and str(used) == requested

# Per-topId coverage matrix (probe results from the 2026-10-02 run):
#   topId=26 (热歌榜)  weekly 2018_30..2024_52, daily 2022-01-01..2024-12-31
#   topId=28 (网络歌曲榜) weekly 2018_30..2024_52
#   topId=78 (国乐榜)   weekly 2018_30..2024_52
#   topId=27 (新歌榜)   weekly 2020_30..2024_52

WEEKLY_RANGES = {
    26: (2018, 30, 2024, 52),
    28: (2018, 30, 2024, 52),
    78: (2018, 30, 2024, 52),
    27: (2020, 30, 2024, 52),
    # extended coverage discovered 2026-10-02:
    5:  (2018, 30, 2024, 52),   # 内地榜
    58: (2020, 30, 2024, 52),   # 说唱榜 (orig 2020_30..)
    57: (2020, 30, 2024, 52),   # 电音榜
    65: (2020, 30, 2024, 52),   # 国风热歌榜
    60: (2020, 30, 2024, 52),   # 抖音热歌榜
}
DAILY_RANGES = {
    26: (2022, 1, 1, 2024, 12, 31),
}

# when a song appears on these charts, we tag it with the implied
# genre. This is how we get *genre* without needing a logged-in
# song-detail endpoint (which QQ blocks at code=500003 since 2024+).
GENRE_TAG_FROM_TOPID = {
    58: "rap",
    57: "edm",
    65: "guofeng",
}

def all_periods_for_topid(top_id: int, density: str = "weekly"):
    out = []
    if density == "weekly" and top_id in WEEKLY_RANGES:
        y0, w0, y1, w1 = WEEKLY_RANGES[top_id]
        for y in range(y0, y1 + 1):
            for w in range(1, 53):
                if (y, w) >= (y0, w0) and (y, w) <= (y1, w1):
                    out.append(f"{y}_{w:02d}")
    elif density == "daily" and top_id in DAILY_RANGES:
        y0, m0, d0, y1, m1, d1 = DAILY_RANGES[top_id]
        d_start = dt.date(y0, m0, d0)
        d_end = dt.date(y1, m1, d1)
        cur = d_start
        while cur <= d_end:
            out.append(cur.isoformat())
            cur += dt.timedelta(days=1)
    return out

def collect_topid(top_id: int, density: str = "weekly",
                  n_issues: int | None = None,
                  sleep_s: float = 0.4) -> Path | None:
    periods = all_periods_for_topid(top_id, density)
    if n_issues:
        periods = periods[:n_issues]
    print(f"[qq] topId={top_id} density={density} -> {len(periods)} periods")

    rows = []
    cache_dir = DATA_RAW / f"topId{top_id}_{density}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for p in periods:
        cache_fp = cache_dir / f"{p}.json"
        if cache_fp.exists():
            d = json.loads(cache_fp.read_text())
        else:
            d = fetch(top_id, p)
            if d is not None:
                cache_fp.write_text(json.dumps(d, ensure_ascii=False))
            time.sleep(sleep_s)
        if not d:
            continue
        info, used = d if isinstance(d, tuple) else (d, None)
        info_dict = info[0] if isinstance(info, tuple) else info
        used_period = info_dict.get("period") if isinstance(info_dict, dict) else None
        if not period_is_valid(used_period, p):
            continue
        title = info_dict.get("title", "")
        listen_num = info_dict.get("listenNum")
        update_time = info_dict.get("updateTime")
        for s in info_dict.get("song", []):
            rows.append({
                "top_id": top_id,
                "top_title": title,
                "period": p,
                "rank": s.get("rank"),
                "song_id": s.get("songId"),
                "song_mid": s.get("songMid"),
                "song_title": s.get("title"),
                "singer_name": s.get("singerName"),
                "singer_mid": s.get("singerMid"),
                "album_mid": s.get("albumMid"),
                "cover": s.get("cover"),
                "song_type": s.get("songType"),
                "rank_value": s.get("rankValue"),
                "rank_type": s.get("rankType"),
                "genre_inferred": GENRE_TAG_FROM_TOPID.get(top_id, ""),
                "chart_listen_num": listen_num,
                "chart_update_time": update_time,
                "fetched_at": dt.date.today().isoformat(),
            })

    if not rows:
        print(f"  ! no usable periods for topId={top_id} {density}", file=sys.stderr)
        return None
    df = pd.DataFrame(rows)
    out_fp = DATA_RAW / f"qq_topId{top_id}_{density}_long.csv"
    df.to_csv(out_fp, index=False, encoding="utf-8-sig")
    print(f"  ok -> {out_fp.relative_to(ROOT)} rows={len(df)}")
    return out_fp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topid", type=int, required=True)
    ap.add_argument("--density", choices=["weekly","daily"], default="weekly")
    ap.add_argument("--n-issues", type=int, default=None,
                    help="limit number of periods for smoke test")
    args = ap.parse_args()
    p = collect_topid(args.topid, args.density, args.n_issues)
    sys.exit(0 if p else 1)

if __name__ == "__main__":
    main()