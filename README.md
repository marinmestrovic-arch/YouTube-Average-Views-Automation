# yt_api

Minimal Python wrapper for the YouTube Data API (v3) with helper functions and a video downloader.

Setup

- Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- Set your YouTube API key in the environment:

```bash
export YT_API_KEY=your_api_key_here
```

Usage

- Example usage is in `examples.py`. Import `YouTubeClient` from `src.youtube_api.client` and call methods like `fetch_channel_info`, `fetch_videos`, and `fetch_video_details`.

Notes

- This is a minimal implementation using `requests` and `yt-dlp` for downloads.
- For production use, handle rate limits and paginated results more robustly.
