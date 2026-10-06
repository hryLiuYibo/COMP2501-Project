#!/usr/bin/env python3
"""Netease Cloud Music current-week toplist collector.

This collector only fetches the *current* toplist (no historical
periods). Netease's API silently ignores any date param we tried.

Use case: cross-platform validation against QQ Music's current toplist.
We compare the snapshot of QQ Hot Songs (topId=26) to Netease Hot Songs
(playlist=3778678) on the same day and ask: which songs appear on
both? Which are platform-specific?

Compliance: public endpoint, no login, no anti-bot bypass.
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
DATA_RAW = ROOT / "data" / "raw" / "netease"
DATA_RAW.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
HDR = {"User-Agent": UA, "Referer": "https://music.163.com/"}

def fetch_playlist_tracks(playlist_id: int) -> list[dict]:
    """Pull all tracks in the playlist via v6 detail + v3 song detail."""
    detail_url = f"https://music.163.com/api/v6/playlist/detail?id={playlist_id}"
    r = requests.get(detail_url, headers=HDR, timeout=15)
    r.raise_for_status()
    pl = r.json().get("playlist", {})
    title = pl.get("name")
    track_ids = [t["id"] for t in pl.get("trackIds", [])]
    update_time_ms = pl.get("updateTime")
    track_count = pl.get("trackCount")

    if not track_ids:
        return [], title, update_time_ms

    # v3 song-detail in chunks of 50
    details = {}
    CHUNK = 50
    for i in range(0, len(track_ids), CHUNK):
        ids = track_ids[i:i + CHUNK]
        c_param = json.dumps([{"id": x} for x in ids], separators=(",", ":"))
        url = "https://music.163.com/api/v3/song/detail?c=" + \
              __import__("urllib.parse").parse.quote(c_param)
        r = requests.get(url, headers=HDR, timeout=15)
        r.raise_for_status()
        for s in r.json().get("songs", []):
            details[s["id"]] = {
                "title": s.get("name"),
                "artist": ",".join(a.get("name", "") for a in s.get("ar", [])),
                "album": (s.get("al") or {}).get("name"),
                "duration_ms": s.get("dt"),
                "publish_ms": s.get("publishTime"),
            }
        time.sleep(0.4)

    rows = []
    for tid in track_ids:
        d = details.get(tid, {})
        pub = d.get("publish_ms") or 0
        year = (dt.datetime.fromtimestamp(pub / 1000,
                tz=__import__("zoneinfo").ZoneInfo("UTC")).year
                if pub > 0 else None)
        rows.append({
            "track_id": tid,
            "title": d.get("title"),
            "artist": d.get("artist"),
            "album": d.get("album"),
            "year": year,
            "duration_ms": d.get("duration_ms"),
            "playlist_id": playlist_id,
            "playlist_title": title,
            "fetched_at": dt.date.today().isoformat(),
            "source_url": f"https://music.163.com/song?id={tid}",
            "netease_update_time_ms": update_time_ms,
        })
    return rows, title, update_time_ms

# Top playlists to fetch (verified public, no login)
DEFAULT_PLAYLISTS = [
    (3778678, "netease_hot_songs"),       # 热歌榜
    (19723756, "netease_soaring"),         # 飙升榜
    (3779629, "netease_new_songs"),       # 新歌榜
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, action="append", default=None,
                    help="playlist id; repeat for multiple")
    ap.add_argument("--label", type=str, action="append", default=None,
                    help="optional label per --id")
    args = ap.parse_args()

    items = []
    if args.id:
        items = [(tid, lab or f"netease_pl_{tid}") for tid, lab in
                 zip(args.id, args.label or [None] * len(args.id))]
    else:
        items = DEFAULT_PLAYLISTS

    for pl_id, label in items:
        try:
            rows, title, _ = fetch_playlist_tracks(pl_id)
        except Exception as e:
            print(f"  ! fail {pl_id}: {e}", file=sys.stderr)
            continue
        if not rows:
            print(f"  ! 0 rows for {pl_id}", file=sys.stderr)
            continue
        df = pd.DataFrame(rows)
        df["label"] = label
        out_fp = DATA_RAW / f"{label}_{pl_id}.csv"
        df.to_csv(out_fp, index=False, encoding="utf-8-sig")
        print(f"  ok playlist={pl_id} '{title}' rows={len(df)} -> "
              f"{out_fp.relative_to(ROOT)}")

if __name__ == "__main__":
    main()