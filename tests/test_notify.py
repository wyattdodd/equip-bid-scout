# tests/test_notify.py
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBuildNotificationBody(unittest.TestCase):

    def _picks(self):
        return [
            {
                "title": "DeWalt 20V MAX Drill Driver Kit",
                "current_bid": "$5.00",
                "est_resale": "$80-$200 (brand: dewalt)",
                "url": "https://www.equip-bid.com/auction/123/item/1",
                "auction_id": "123",
                "auction_title": "Wichita Industrial Tools",
                "closing_utc": "2026-04-22 20:00:00 UTC",
            },
            {
                "title": "Milwaukee M18 Impact Wrench — Retails for $249",
                "current_bid": "$0.00",
                "est_resale": "~$249 (stated retail)",
                "url": "https://www.equip-bid.com/auction/123/item/2",
                "auction_id": "123",
                "auction_title": "Wichita Industrial Tools",
                "closing_utc": "2026-04-22 20:00:00 UTC",
            },
        ]

    def test_body_contains_auction_title(self):
        from equip_bid_notify import build_notification_body
        body = build_notification_body("123", self._picks())
        self.assertIn("Wichita Industrial Tools", body)

    def test_body_contains_item_titles(self):
        from equip_bid_notify import build_notification_body
        body = build_notification_body("123", self._picks())
        self.assertIn("DeWalt 20V MAX Drill Driver Kit", body)
        self.assertIn("Milwaukee M18 Impact Wrench", body)

    def test_body_contains_bids(self):
        from equip_bid_notify import build_notification_body
        body = build_notification_body("123", self._picks())
        self.assertIn("$5.00", body)
        self.assertIn("$0.00", body)

    def test_body_contains_auction_url(self):
        from equip_bid_notify import build_notification_body
        body = build_notification_body("123", self._picks())
        self.assertIn("equip-bid.com/auction/123", body)

    def test_empty_picks_raises(self):
        from equip_bid_notify import build_notification_body
        with self.assertRaises(ValueError):
            build_notification_body("123", [])


class TestFilterPicks(unittest.TestCase):

    def _data(self):
        return {
            "picks": [
                {"auction_id": "123", "title": "Item A"},
                {"auction_id": "123", "title": "Item B"},
                {"auction_id": "456", "title": "Item C"},
            ]
        }

    def test_returns_picks_for_matching_auction(self):
        from equip_bid_notify import filter_picks
        result = filter_picks(self._data(), "123")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "Item A")

    def test_returns_empty_for_nonmatching_auction(self):
        from equip_bid_notify import filter_picks
        result = filter_picks(self._data(), "999")
        self.assertEqual(result, [])

    def test_returns_empty_for_empty_data(self):
        from equip_bid_notify import filter_picks
        result = filter_picks({"picks": []}, "123")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
