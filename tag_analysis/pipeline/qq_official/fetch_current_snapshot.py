#!/usr/bin/env python3
"""QQ Music Hot Songs current-snapshot collector.

Pulls the current top 200 of the QQ Hot Songs chart (topId=26).
Used for cross-region snapshot comparison in Section 9.2 of the
report (against Apple Music CN / US and NetEase).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw" / "qq"
DATA_RAW.mkdir(parents=True, exist_ok=True)

URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36",
       "Referer": "https://y.qq.com/",
       "Content-Type": "application/json; charset=utf-8"}

def fetch_top(top_id: int = 26, num: int = 200) -> dict:
    payload = {"comm": {"ct": 24, "cv": 0},
               "detail": {"module": "musicToplist.ToplistInfoServer",
                          "method": "GetDetail",
                          "param": {"topId": top_id, "offset": 0,
                                    "num": num, "period": ""}}}
    r = requests.post(URL, headers=HDR, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["detail"]["data"]["data"]

def main():
    info = fetch_top(top_id=26, num=200)
    period = info.get("period")
    today = dt.date.today().isoformat()
    rows = []
    for s in info.get("song", []):
        rows.append({
            "rank": s.get("rank"),
            "song_id": s.get("songId"),
            "song_mid": s.get("songMid"),
            "song_title": s.get("title"),
            "singer_name": s.get("singerName"),
            "album_mid": s.get("albumMid"),
            "period": period,
            "top_title": info.get("title"),
            "fetched_at": today,
        })
    df = pd.DataFrame(rows)
    out = DATA_RAW / f"qq_topId26_current_snapshot.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"  ok topId=26 num={len(df)} period={period} -> {out}")

if __name__ == "__main__":
    main()