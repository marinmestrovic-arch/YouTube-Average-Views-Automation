import unittest

from src.youtube_api.client import YouTubeClient


def _channel_id(token: str) -> str:
    return "UC" + token * 22


class StubYouTubeClient(YouTubeClient):
    def __init__(self, handler):
        self.api_key = "test-key"
        self._handler = handler
        self.calls = []

    def _get(self, path, params):
        params = dict(params)
        self.calls.append((path, params))
        return self._handler(path, params)


class YouTubeClientResolutionTests(unittest.TestCase):
    def test_non_youtube_url_is_rejected_without_api_call(self):
        client = StubYouTubeClient(lambda *_: self.fail("No API call expected for unsupported URL host"))

        with self.assertRaisesRegex(ValueError, "not a supported YouTube channel/video URL"):
            client.resolve_channel_id("https://example.com/@tomoutdoor")

        self.assertEqual(client.calls, [])

    def test_resolve_channel_url_direct_id_without_api_call(self):
        expected = _channel_id("a")
        client = StubYouTubeClient(lambda *_: self.fail("No API call expected for direct channel URL"))

        resolved = client.resolve_channel_id(f"https://www.youtube.com/channel/{expected}")

        self.assertEqual(resolved, expected)
        self.assertEqual(client.calls, [])

    def test_resolve_handle_url_uses_for_handle(self):
        expected = _channel_id("b")

        def handler(path, params):
            self.assertEqual(path, "channels")
            self.assertEqual(params, {"part": "id", "forHandle": "tomoutdoor"})
            return {"items": [{"id": expected}]}

        client = StubYouTubeClient(handler)
        resolved = client.resolve_channel_id("https://www.youtube.com/@tomoutdoor/videos")

        self.assertEqual(resolved, expected)
        self.assertEqual(len(client.calls), 1)

    def test_resolve_watch_url_uses_video_owner_channel(self):
        expected = _channel_id("c")

        def handler(path, params):
            self.assertEqual(path, "videos")
            self.assertEqual(params, {"part": "snippet", "id": "BTQ6Sf_XC68"})
            return {"items": [{"snippet": {"channelId": expected}}]}

        client = StubYouTubeClient(handler)
        resolved = client.resolve_channel_id("https://www.youtube.com/watch?v=BTQ6Sf_XC68")

        self.assertEqual(resolved, expected)
        self.assertEqual(len(client.calls), 1)

    def test_plain_handle_prefers_for_handle_over_username_and_search(self):
        expected = _channel_id("d")

        def handler(path, params):
            if path == "channels" and "forHandle" in params:
                self.assertEqual(params, {"part": "id", "forHandle": "tomoutdoor"})
                return {"items": [{"id": expected}]}
            self.fail(f"Unexpected fallback call path={path} params={params}")

        client = StubYouTubeClient(handler)
        resolved = client.resolve_channel_id("tomoutdoor")

        self.assertEqual(resolved, expected)
        self.assertEqual(client.calls, [("channels", {"part": "id", "forHandle": "tomoutdoor"})])

    def test_fetch_videos_handle_url_uses_for_handle_content_details(self):
        expected_channel_id = _channel_id("e")

        def handler(path, params):
            if path == "channels":
                self.assertEqual(params, {"part": "contentDetails", "forHandle": "tomoutdoor"})
                return {
                    "items": [
                        {
                            "id": expected_channel_id,
                            "contentDetails": {"relatedPlaylists": {"uploads": "UU_uploads"}},
                        }
                    ]
                }
            if path == "playlistItems":
                self.assertEqual(params, {"part": "snippet,contentDetails", "playlistId": "UU_uploads", "maxResults": 1})
                return {
                    "items": [
                        {
                            "contentDetails": {"videoId": "BTQ6Sf_XC68"},
                            "snippet": {"title": "Video", "publishedAt": "2026-02-23T14:00:13Z"},
                        }
                    ]
                }
            if path == "videos":
                self.assertEqual(
                    params,
                    {"part": "snippet,contentDetails,statistics", "id": "BTQ6Sf_XC68"},
                )
                return {
                    "items": [
                        {
                            "id": "BTQ6Sf_XC68",
                            "contentDetails": {"duration": "PT10M"},
                            "statistics": {"viewCount": "1234"},
                            "snippet": {"thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}}},
                        }
                    ]
                }
            self.fail(f"Unexpected API call path={path} params={params}")

        client = StubYouTubeClient(handler)
        videos = client.fetch_videos("https://youtube.com/@tomoutdoor", max_results=1)

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["id"], "BTQ6Sf_XC68")
        self.assertEqual(videos[0]["viewCount"], "1234")
        self.assertEqual(client.calls[0], ("channels", {"part": "contentDetails", "forHandle": "tomoutdoor"}))


if __name__ == "__main__":
    unittest.main()
