import subprocess
from pathlib import Path
from typing import Optional


def download_video(video_id: str, output_path: str = "downloads", quality: str = "best") -> str:
    """Download a YouTube video using yt-dlp and return the output directory.

    `quality` is a format specifier passed to `yt-dlp -f`.
    """
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp",
        "-f",
        quality,
        "-o",
        str(out_dir / "%(title)s-%(id)s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")
    return str(out_dir)
