#!/usr/bin/env python3
"""Rebuild the long-format CSV from the cached per-period JSON files.

Used after we add new columns (genre_inferred, chart_listen_num, etc.)
to the collector — rather than re-hit QQ, we just re-parse the cached
JSON to drop a fresh CSV with the new schema.

JSON side-effects of the same fetch() function were stored as a 2-list
[info_dict, used_period]. Each info_dict already has listenNum /
updateTime / song[] at the top level.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw" / "qq"
DATA_RAW.mkdir(parents=True, exist_ok=True)

GENRE_TAG_FROM_TOPID = {
    58: "rap",
    57: "edm",
    65: "guofeng",
}

def rebuild(top_id: int, density: str = "weekly"):
    cache_dir = DATA_RAW / f"topId{top_id}_{density}"
    if not cache_dir.exists():
        print(f"  ! no cache dir {cache_dir}", file=sys.stderr)
        return None
    files = sorted(cache_dir.glob("*.json"))
    if not files:
        print(f"  ! no JSONs in {cache_dir}", file=sys.stderr)
        return None
    rows = []
    for fp in files:
        try:
            cached = json.loads(fp.read_text())
        except Exception as e:
            print(f"  skip {fp.name}: {e}", file=sys.stderr)
            continue
        if not isinstance(cached, list) or len(cached) < 1:
            continue
        info = cached[0]
        period = info.get("period")
        if not period:
            continue
        title = info.get("title", "")
        listen_num = info.get("listenNum")
        update_time = info.get("updateTime")
        for s in info.get("song", []):
            rows.append({
                "top_id": top_id,
                "top_title": title,
                "period": period,
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
        print(f"  ! 0 rows from cache topId={top_id}", file=sys.stderr)
        return None
    df = pd.DataFrame(rows)
    out = DATA_RAW / f"qq_topId{top_id}_{density}_long.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"  ok topId={top_id} density={density} -> "
          f"{out.relative_to(ROOT)} rows={len(df)}")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topid", type=int, action="append", required=True,
                    help="repeat for each topId")
    ap.add_argument("--density", action="append", default=None,
                    help="density for the previous --topid (same order)")
    args = ap.parse_args()
    if args.density is None:
        args.density = ["weekly"] * len(args.topid)
    if len(args.density) == 1 and len(args.topid) > 1:
        args.density = args.density * len(args.topid)
    if len(args.density) != len(args.topid):
        print("--topid / --density length mismatch", file=sys.stderr)
        sys.exit(1)
    for tid, den in zip(args.topid, args.density):
        rebuild(tid, den)

if __name__ == "__main__":
    main()