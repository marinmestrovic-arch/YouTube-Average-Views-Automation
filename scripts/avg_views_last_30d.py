#!/usr/bin/env python3
"""Compute average views in the last 30 days for videos longer than X minutes.

Usage:
    python scripts/avg_views_last_30d.py <channel_identifier> [API_KEY]

Examples:
    python scripts/avg_views_last_30d.py "@veritasium"
    python scripts/avg_views_last_30d.py UC_xxx YOUR_API_KEY
"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import List

from dateutil import parser as date_parser

# Ensure project root is on sys.path so `src` package can be imported when
# running the script from the repository root or other locations.
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.youtube_api.client import YouTubeClient


def iso8601_duration_to_minutes(dur: str) -> float:
    hours = minutes = seconds = 0
    match = re.match(r"P(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)", dur or "")
    if not match:
        return 0.0
    h, m, s = match.groups()
    if h:
        hours = int(h)
    if m:
        minutes = int(m)
    if s:
        seconds = int(s)
    return hours * 60 + minutes + seconds / 60.0


def avg_views_last_30d(client: YouTubeClient, channel_identifier: str, min_minutes: int = 3, fetch_count: int = 50) -> float:
    """Return average view count for videos published in last 30 days and longer than min_minutes.

    - `fetch_count` controls how many recent videos to fetch from the uploads playlist.
    """
    videos = client.fetch_videos(channel_identifier, max_results=fetch_count)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    matching_views: List[int] = []
    for v in videos:
        pub = v.get("publishedAt")
        if not pub:
            continue
        try:
            pub_dt = date_parser.parse(pub)
        except Exception:
            continue
        if pub_dt < cutoff:
            continue
        dur_iso = v.get("duration", "PT0S")
        dur_min = iso8601_duration_to_minutes(dur_iso)
        if dur_min < min_minutes:
            continue
        view = v.get("viewCount") or 0
        try:
            view_int = int(view)
        except Exception:
            try:
                view_int = int(float(view))
            except Exception:
                view_int = 0
        matching_views.append(view_int)
    if not matching_views:
        return 0.0
    return sum(matching_views) / len(matching_views)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: avg_views_last_30d.py <channel_identifier> [API_KEY]")
        sys.exit(1)
    identifier = sys.argv[1]
    api_key = sys.argv[2] if len(sys.argv) > 2 else None
    client = YouTubeClient(api_key) if api_key else YouTubeClient()
    avg = avg_views_last_30d(client, identifier)
    print(f"Average views (last 30 days, >3min): {avg:.2f}")


if __name__ == "__main__":
    main()
