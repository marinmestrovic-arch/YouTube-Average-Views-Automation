import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import requests
from dateutil import parser as date_parser


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def _iso8601_duration_to_minutes(dur: str) -> float:
    """Convert ISO8601 duration (e.g. PT1H2M3S) to minutes."""
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


class YouTubeClient:
    """Minimal YouTube Data API v3 client using an API key."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("YT_API_KEY")
        if not self.api_key:
            raise ValueError("You must provide a YouTube API key via parameter or YT_API_KEY env var")

    def _get(self, path: str, params: Dict[str, Any]) -> Dict:
        params = params.copy()
        params["key"] = self.api_key
        resp = requests.get(f"{YOUTUBE_API_BASE}/{path}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def resolve_channel_id(self, identifier: str) -> str:
        """Resolve a handle, URL, or channel ID to the canonical channel ID."""
        if identifier.startswith("UC") and len(identifier) > 20:
            return identifier
        identifier = identifier.strip()
        if identifier.startswith("http"):
            parts = identifier.rstrip("/").split("/")
            possible = parts[-1]
            if possible.startswith("UC"):
                return possible
            identifier = possible
        data = self._get("search", {"part": "snippet", "q": identifier, "type": "channel", "maxResults": 1})
        items = data.get("items", [])
        if not items:
            raise ValueError(f"Channel not found for identifier: {identifier}")
        return items[0]["snippet"]["channelId"]

    def fetch_channel_info(self, channel_id: str) -> Dict:
        """Fetch channel snippet, statistics, and content details."""
        channel_id = self.resolve_channel_id(channel_id)
        data = self._get("channels", {"part": "snippet,statistics,contentDetails", "id": channel_id})
        items = data.get("items", [])
        if not items:
            raise ValueError("Channel not found")
        item = items[0]
        return {
            "id": item.get("id"),
            "title": item.get("snippet", {}).get("title"),
            "description": item.get("snippet", {}).get("description"),
            "thumbnails": item.get("snippet", {}).get("thumbnails"),
            "subscriberCount": item.get("statistics", {}).get("subscriberCount"),
            "viewCount": item.get("statistics", {}).get("viewCount"),
            "videoCount": item.get("statistics", {}).get("videoCount"),
            "contentDetails": item.get("contentDetails"),
        }

    def fetch_videos(self, channel_id: str, max_results: int = 10) -> List[Dict]:
        """Return recent videos from the channel uploads playlist with basic details."""
        channel_id = self.resolve_channel_id(channel_id)
        ch = self._get("channels", {"part": "contentDetails", "id": channel_id})
        items = ch.get("items", [])
        if not items:
            return []
        uploads_playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        videos = []
        next_page_token = None
        while len(videos) < max_results:
            params = {"part": "snippet,contentDetails", "playlistId": uploads_playlist, "maxResults": min(50, max_results - len(videos))}
            if next_page_token:
                params["pageToken"] = next_page_token
            data = self._get("playlistItems", params)
            for it in data.get("items", []):
                videos.append({
                    "id": it["contentDetails"]["videoId"],
                    "title": it["snippet"]["title"],
                    "publishedAt": it["snippet"]["publishedAt"],
                })
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
        ids = ",".join([v["id"] for v in videos])
        if ids:
            details = self._get("videos", {"part": "snippet,contentDetails,statistics", "id": ids})
            stats_map = {it["id"]: it for it in details.get("items", [])}
            out = []
            for v in videos:
                d = stats_map.get(v["id"], {})
                out.append({
                    **v,
                    "duration": d.get("contentDetails", {}).get("duration"),
                    "viewCount": d.get("statistics", {}).get("viewCount"),
                    "likeCount": d.get("statistics", {}).get("likeCount"),
                    "commentCount": d.get("statistics", {}).get("commentCount"),
                    "thumbnails": d.get("snippet", {}).get("thumbnails"),
                })
            return out
        return videos

    def fetch_video_details(self, video_id: str) -> Dict:
        """Fetch video snippet, content details, and statistics for a single video."""
        data = self._get("videos", {"part": "snippet,contentDetails,statistics", "id": video_id})
        items = data.get("items", [])
        if not items:
            raise ValueError("Video not found")
        it = items[0]
        return {
            "id": it.get("id"),
            "title": it.get("snippet", {}).get("title"),
            "description": it.get("snippet", {}).get("description"),
            "publishedAt": it.get("snippet", {}).get("publishedAt"),
            "duration": it.get("contentDetails", {}).get("duration"),
            "viewCount": it.get("statistics", {}).get("viewCount"),
            "likeCount": it.get("statistics", {}).get("likeCount"),
            "commentCount": it.get("statistics", {}).get("commentCount"),
            "thumbnails": it.get("snippet", {}).get("thumbnails"),
        }

    def fetch_comments(self, video_id: str, max_results: int = 100) -> List[Dict]:
        """Return top-level comments for a video."""
        comments = []
        next_page = None
        while len(comments) < max_results:
            params = {"part": "snippet", "videoId": video_id, "maxResults": min(100, max_results - len(comments))}
            if next_page:
                params["pageToken"] = next_page
            data = self._get("commentThreads", params)
            for it in data.get("items", []):
                sn = it["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "id": it["id"],
                    "author": sn.get("authorDisplayName"),
                    "text": sn.get("textDisplay"),
                    "likeCount": sn.get("likeCount"),
                    "publishedAt": sn.get("publishedAt"),
                })
            next_page = data.get("nextPageToken")
            if not next_page:
                break
        return comments

    def search_youtube_channels(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search for channels matching `query`."""
        data = self._get("search", {"part": "snippet", "type": "channel", "q": query, "maxResults": max_results})
        out = []
        for it in data.get("items", []):
            out.append({
                "id": it["snippet"]["channelId"],
                "title": it["snippet"]["title"],
                "description": it["snippet"].get("description"),
                "thumbnails": it["snippet"].get("thumbnails"),
            })
        return out

    def search_and_introspect_channel(self, query: str, video_count: int = 5) -> Dict:
        """Search for a channel and return its info plus recent videos."""
        channels = self.search_youtube_channels(query, max_results=1)
        if not channels:
            raise ValueError("No channel found for query")
        ch_id = channels[0]["id"]
        info = self.fetch_channel_info(ch_id)
        videos = self.fetch_videos(ch_id, max_results=video_count)
        return {"channel": info, "videos": videos}

    def introspect_channel(self, identifier: str, max_videos: int = 10) -> Dict:
        """Resolve identifier and return channel info with recent videos."""
        ch_id = self.resolve_channel_id(identifier)
        info = self.fetch_channel_info(ch_id)
        videos = self.fetch_videos(ch_id, max_results=max_videos)
        return {"channel": info, "videos": videos}

    def search_youtube_channel_videos(self, channel_id: str, search_term: str, max_results: int = 10) -> List[Dict]:
        """Search videos within a channel by term and return details."""
        channel_id = self.resolve_channel_id(channel_id)
        data = self._get("search", {"part": "snippet", "channelId": channel_id, "q": search_term, "type": "video", "maxResults": max_results})
        out = []
        ids = []
        for it in data.get("items", []):
            vid = it["id"]["videoId"]
            ids.append(vid)
            out.append({"id": vid, "title": it["snippet"]["title"], "publishedAt": it["snippet"]["publishedAt"]})
        if ids:
            details = self._get("videos", {"part": "contentDetails,statistics,snippet", "id": ",".join(ids)})
            mapd = {it["id"]: it for it in details.get("items", [])}
            for o in out:
                d = mapd.get(o["id"], {})
                o.update({
                    "duration": d.get("contentDetails", {}).get("duration"),
                    "viewCount": d.get("statistics", {}).get("viewCount"),
                })
        return out

    def fetch_video_statistics(self, channel_id: str, max_results: int = 10, months: int = 6, min_duration_minutes: int = 3) -> List[Dict]:
        """Return statistics for recent videos filtered by recency and duration."""
        videos = self.fetch_videos(channel_id, max_results=max_results * 2)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
        filtered = []
        for v in videos:
            pub = date_parser.parse(v.get("publishedAt"))
            dur = v.get("duration") or "PT0S"
            dur_min = _iso8601_duration_to_minutes(dur)
            if pub >= cutoff and dur_min >= min_duration_minutes:
                filtered.append({
                    "videoId": v.get("id"),
                    "publishedAt": v.get("publishedAt"),
                    "durationMinutes": dur_min,
                    "viewCount": v.get("viewCount"),
                    "likeCount": v.get("likeCount"),
                    "commentCount": v.get("commentCount"),
                })
                if len(filtered) >= max_results:
                    break
        return filtered
