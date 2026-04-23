# tests/test_dispatcher.py
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_row(auction_id="123", topic="my-topic"):
    return {
        "id": "row-uuid-1",
        "auction_id": auction_id,
        "ntfy_topic": topic,
        "items": [
            {
                "title": "DeWalt 20V MAX Drill Driver Kit",
                "current_bid": "$5.00",
                "est_resale": "$80-$200 (brand: dewalt)",
                "auction_title": "Wichita Industrial Tools",
            }
        ],
    }


class TestDispatcherBuildNtfyBody(unittest.TestCase):

    def test_contains_auction_title(self):
        from scripts.dispatcher import build_ntfy_body
        body = build_ntfy_body("123", _make_row()["items"])
        self.assertIn("Wichita Industrial Tools", body)

    def test_contains_item_title(self):
        from scripts.dispatcher import build_ntfy_body
        body = build_ntfy_body("123", _make_row()["items"])
        self.assertIn("DeWalt 20V MAX Drill Driver Kit", body)

    def test_contains_bid(self):
        from scripts.dispatcher import build_ntfy_body
        body = build_ntfy_body("123", _make_row()["items"])
        self.assertIn("$5.00", body)

    def test_contains_est_resale(self):
        from scripts.dispatcher import build_ntfy_body
        body = build_ntfy_body("123", _make_row()["items"])
        self.assertIn("$80-$200", body)

    def test_contains_auction_url(self):
        from scripts.dispatcher import build_ntfy_body
        body = build_ntfy_body("123", _make_row()["items"])
        self.assertIn("equip-bid.com/auction/123", body)


class TestPostNtfy(unittest.TestCase):

    def test_posts_to_correct_url(self):
        from scripts.dispatcher import post_ntfy
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        with patch("scripts.dispatcher.requests.post", return_value=mock_resp) as mock_post:
            post_ntfy("my-topic", "test body")
        call_url = mock_post.call_args[0][0]
        self.assertIn("ntfy.sh/my-topic", call_url)

    def test_raises_on_http_error(self):
        from scripts.dispatcher import post_ntfy
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("500")
        with patch("scripts.dispatcher.requests.post", return_value=mock_resp):
            with self.assertRaises(req.HTTPError):
                post_ntfy("my-topic", "test body")


if __name__ == "__main__":
    unittest.main()
