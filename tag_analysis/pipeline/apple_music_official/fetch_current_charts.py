#!/usr/bin/env python3
"""Apple Music RSS public charts collector (current snapshot only).

Apple publishes a public RSS feed at
  https://rss.applemarketingtools.com/api/v2/<region>/music/most-played/50/songs.json

It is a CURRENT snapshot only — no historical API exists. This
collector pulls the current week's top 50 for one region.
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
DATA_RAW = ROOT / "data" / "raw" / "apple_music"
DATA_RAW.mkdir(parents=True, exist_ok=True)

URL = "https://rss.applemarketingtools.com/api/v2/{region}/music/most-played/50/songs.json"
HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}

def fetch(region: str, retries: int = 3):
    url = URL.format(region=region)
    for i in range(retries):
        try:
            r = requests.get(url, headers=HDR, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  retry {i+1}/{retries} region={region}: {e}", file=sys.stderr)
            time.sleep(2)
    return None

def parse(d: dict, region: str) -> pd.DataFrame:
    feed = d.get("feed", {})
    results = feed.get("results", [])
    rows = []
    for i, r in enumerate(results, 1):
        rows.append({
            "rank": i,
            "id": r.get("id"),
            "name": r.get("name"),
            "artist_name": r.get("artistName"),
            "composer_name": r.get("composerName"),
            "release_date": r.get("releaseDate"),
            "duration_ms": r.get("durationInMillis"),
            "apple_music_url": r.get("url"),
            "artwork_url": (r.get("artworkUrl100") or r.get("artworkUrl60")),
        })
    df = pd.DataFrame(rows)
    df["region"] = region
    df["country"] = feed.get("country", region)
    df["feed_updated"] = feed.get("updated")
    df["fetched_at"] = dt.date.today().isoformat()
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", action="append", required=True,
                    help="region code (e.g. cn, us, jp, gb). repeat.")
    args = ap.parse_args()
    for region in args.region:
        d = fetch(region)
        if not d:
            print(f"  ! {region}: 0 rows", file=sys.stderr)
            continue
        df = parse(d, region)
        if df.empty:
            print(f"  ! {region}: parse 0 rows", file=sys.stderr)
            continue
        today = dt.date.today().isoformat()
        out = DATA_RAW / f"apple_music_{region}_top50_{today}.csv"
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"  ok {region}: {len(df)} rows -> {out.relative_to(ROOT)}")

if __name__ == "__main__":
    main()