import os

import os
from src.youtube_api.client import YouTubeClient
from src.youtube_api.helpers import download_video


def main():
    key = os.environ.get("YT_API_KEY")
    if not key:
        print("Set YT_API_KEY in your environment before running the example.")
        return
    client = YouTubeClient(key)

    # Example: fetch channel info for a known channel (replace with desired id/handle)
    print("Fetching channel info for 'veritasium' (search):")
    info = client.introspect_channel("@veritasium", max_videos=3)
    print(info)

    # Example: fetch video details (replace with an actual video ID if desired)
    # vid = info['videos'][0]['id']
    # details = client.fetch_video_details(vid)
    # print(details)

    # Example: download video (uncomment to run, requires yt-dlp installed)
    # download_video(vid, output_path='downloads', quality='best')


if __name__ == "__main__":
    main()
