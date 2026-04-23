# tests/test_check.py
import sys
import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from equip_bid_check import parse_closing_utc, build_body


class TestParseClosingUtc(unittest.TestCase):

    def test_parses_valid_utc_string(self):
        dt = parse_closing_utc("2026-04-22 20:00:00 UTC")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 4)
        self.assertEqual(dt.day, 22)
        self.assertEqual(dt.hour, 20)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_returns_none_for_none(self):
        self.assertIsNone(parse_closing_utc(None))

    def test_returns_none_for_empty_string(self):
        self.assertIsNone(parse_closing_utc(""))

    def test_returns_none_for_garbage(self):
        self.assertIsNone(parse_closing_utc("not a date"))

    def test_result_is_utc_aware(self):
        dt = parse_closing_utc("2026-06-01 12:00:00 UTC")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_30_min_before_close_is_correct(self):
        dt = parse_closing_utc("2026-04-22 20:00:00 UTC")
        trigger = dt - timedelta(minutes=30)
        self.assertEqual(trigger.hour, 19)
        self.assertEqual(trigger.minute, 30)


class TestBuildBody(unittest.TestCase):

    def _picks(self):
        return [
            {
                "title": "DeWalt 20V MAX Drill Driver Kit",
                "current_bid": "$5.00",
                "est_resale": "$80-$200 (brand: dewalt)",
                "auction_id": "123",
                "auction_title": "Wichita Industrial Tools",
                "closing_utc": "2026-04-22 20:00:00 UTC",
            },
            {
                "title": "Milwaukee M18 Impact Wrench",
                "current_bid": "$0.00",
                "est_resale": "~$249 (stated retail)",
                "auction_id": "123",
                "auction_title": "Wichita Industrial Tools",
                "closing_utc": "2026-04-22 20:00:00 UTC",
            },
        ]

    def test_body_contains_auction_title(self):
        body = build_body("123", self._picks())
        self.assertIn("Wichita Industrial Tools", body)

    def test_body_contains_item_titles(self):
        body = build_body("123", self._picks())
        self.assertIn("DeWalt 20V MAX Drill Driver Kit", body)
        self.assertIn("Milwaukee M18 Impact Wrench", body)

    def test_body_contains_bids(self):
        body = build_body("123", self._picks())
        self.assertIn("$5.00", body)
        self.assertIn("$0.00", body)

    def test_body_contains_est_resale(self):
        body = build_body("123", self._picks())
        self.assertIn("$80-$200", body)

    def test_body_contains_auction_url(self):
        body = build_body("123", self._picks())
        self.assertIn("equip-bid.com/auction/123", body)

    def test_single_pick_produces_valid_body(self):
        body = build_body("456", [self._picks()[0]])
        self.assertIn("DeWalt", body)
        self.assertIn("equip-bid.com/auction/456", body)

    def test_falls_back_auction_title_when_missing(self):
        pick = {"title": "Some Item", "current_bid": "$1.00", "est_resale": "?"}
        body = build_body("789", [pick])
        self.assertIn("Auction 789", body)


class TestAlertWindow(unittest.TestCase):
    """Verify the 20-55 minute alert window logic used in main()."""

    ALERT_MIN = 20
    ALERT_MAX = 55

    def _in_window(self, minutes_left):
        return self.ALERT_MIN <= minutes_left <= self.ALERT_MAX

    def test_30_min_left_is_in_window(self):
        self.assertTrue(self._in_window(30))

    def test_20_min_left_is_in_window(self):
        self.assertTrue(self._in_window(20))

    def test_55_min_left_is_in_window(self):
        self.assertTrue(self._in_window(55))

    def test_19_min_left_is_outside_window(self):
        self.assertFalse(self._in_window(19))

    def test_56_min_left_is_outside_window(self):
        self.assertFalse(self._in_window(56))

    def test_already_closed_is_outside_window(self):
        self.assertFalse(self._in_window(-5))

    def test_notification_sent_for_auction_in_window(self):
        """main() calls requests.post when an auction is in the alert window."""
        now = datetime(2026, 4, 22, 19, 35, 0, tzinfo=timezone.utc)
        closing_utc = "2026-04-22 20:00:00 UTC"  # 25 min away — in window

        import json, tempfile, os
        from equip_bid_check import parse_closing_utc, build_body

        picks = [{
            "title": "DeWalt Drill",
            "current_bid": "$5.00",
            "est_resale": "$80-$200",
            "auction_id": "123",
            "auction_title": "Wichita Tools",
            "closing_utc": closing_utc,
        }]
        data = {"picks": picks}

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            json.dump(data, f)
            path = f.name

        try:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            with patch("equip_bid_check.WATCHLIST_PATH", new=__import__("pathlib").Path(path)), \
                 patch("equip_bid_check.datetime") as mock_dt, \
                 patch("equip_bid_check.requests.post", return_value=mock_resp) as mock_post:
                mock_dt.now.return_value = now
                mock_dt.strptime = datetime.strptime
                import equip_bid_check
                equip_bid_check.main()
            mock_post.assert_called_once()
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
