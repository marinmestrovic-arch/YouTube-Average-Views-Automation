#!/usr/bin/env python3
"""
Search for YouTube channels based on a query prompt.

Usage:
    python search_channels.py "channel name"
"""

import sys
import json
from pathlib import Path

# Add src directory to path so we can import youtube_api
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from youtube_api.client import YouTubeClient


def main():
    if len(sys.argv) < 2:
        print("Usage: python search_channels.py <query>")
        print("Example: python search_channels.py 'MrBeast'")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    
    try:
        client = YouTubeClient()
        print(f"Searching for channels matching: '{query}'...\n")
        
        results = client.search_youtube_channels(query, max_results=10)
        
        if not results:
            print("No channels found.")
            return
        
        print(f"Found {len(results)} channel(s):\n")
        for i, channel in enumerate(results, 1):
            print(f"{i}. {channel['title']}")
            print(f"   ID: {channel['id']}")
            if channel.get('description'):
                desc = channel['description']
                if len(desc) > 100:
                    desc = desc[:100] + "..."
                print(f"   Description: {desc}")
            print()
    
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
