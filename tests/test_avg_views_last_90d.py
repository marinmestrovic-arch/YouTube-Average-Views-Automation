import unittest
from datetime import datetime, timedelta, timezone

from scripts.avg_views_last_90d import avg_views_last_90d


class StubClient:
    def __init__(self, videos):
        self._videos = videos

    def fetch_videos(self, channel_identifier, max_results=10):
        return self._videos[:max_results]


class AvgViewsLast90dTests(unittest.TestCase):
    def test_uses_90_day_window_and_min_duration(self):
        now = datetime.now(timezone.utc)
        videos = [
            {
                "publishedAt": (now - timedelta(days=10)).isoformat(),
                "duration": "PT10M",
                "viewCount": "100",
            },
            {
                "publishedAt": (now - timedelta(days=85)).isoformat(),
                "duration": "PT5M",
                "viewCount": "300",
            },
            {
                "publishedAt": (now - timedelta(days=95)).isoformat(),
                "duration": "PT8M",
                "viewCount": "1000",
            },
            {
                "publishedAt": (now - timedelta(days=3)).isoformat(),
                "duration": "PT2M59S",
                "viewCount": "900",
            },
        ]
        client = StubClient(videos)

        result = avg_views_last_90d(client, "any-channel", min_minutes=3, fetch_count=25)

        self.assertEqual(result, 200.0)

    def test_window_days_override(self):
        now = datetime.now(timezone.utc)
        videos = [
            {
                "publishedAt": (now - timedelta(days=10)).isoformat(),
                "duration": "PT10M",
                "viewCount": "100",
            },
            {
                "publishedAt": (now - timedelta(days=40)).isoformat(),
                "duration": "PT10M",
                "viewCount": "500",
            },
        ]
        client = StubClient(videos)

        result = avg_views_last_90d(
            client,
            "any-channel",
            min_minutes=3,
            fetch_count=25,
            window_days=30,
        )

        self.assertEqual(result, 100.0)


if __name__ == "__main__":
    unittest.main()
