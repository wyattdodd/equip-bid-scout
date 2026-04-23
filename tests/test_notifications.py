# tests/test_notifications.py
import sys
import os
import unittest
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_items(auction_id="123", auction_title="Wichita Industrial Tools"):
    return [
        {
            "title": "DeWalt 20V MAX Drill Driver Kit",
            "current_bid": "$5.00",
            "est_resale": "$80-$200 (brand: dewalt)",
            "url": f"https://www.equip-bid.com/auction/{auction_id}/item/1",
            "auction_id": auction_id,
            "auction_title": auction_title,
            "closing_utc": "2099-12-31 23:00:00 UTC",
        }
    ]


class TestBuildNtfyBody(unittest.TestCase):

    def test_contains_auction_title(self):
        from services.notifications import build_ntfy_body
        body = build_ntfy_body("123", _make_items())
        self.assertIn("Wichita Industrial Tools", body)

    def test_contains_item_title(self):
        from services.notifications import build_ntfy_body
        body = build_ntfy_body("123", _make_items())
        self.assertIn("DeWalt 20V MAX Drill Driver Kit", body)

    def test_contains_bid(self):
        from services.notifications import build_ntfy_body
        body = build_ntfy_body("123", _make_items())
        self.assertIn("$5.00", body)

    def test_contains_est_resale(self):
        from services.notifications import build_ntfy_body
        body = build_ntfy_body("123", _make_items())
        self.assertIn("$80-$200", body)

    def test_contains_auction_url(self):
        from services.notifications import build_ntfy_body
        body = build_ntfy_body("123", _make_items())
        self.assertIn("equip-bid.com/auction/123", body)

    def test_empty_items_raises_value_error(self):
        from services.notifications import build_ntfy_body
        with self.assertRaises(ValueError):
            build_ntfy_body("123", [])

    def test_falls_back_auction_title_when_missing(self):
        from services.notifications import build_ntfy_body
        items = [{"title": "Widget", "current_bid": "$1.00", "est_resale": "?"}]
        body = build_ntfy_body("789", items)
        self.assertIn("Auction 789", body)


class TestScheduleNotifications(unittest.TestCase):

    def _make_mock_client(self):
        mock = MagicMock()
        # Chain: .table().delete().eq().eq().execute()
        mock.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        # Chain: .table().insert().execute()
        mock.table.return_value.insert.return_value.execute.return_value = MagicMock()
        return mock

    def _make_picks(self, closing_utc="2099-12-31 23:00:00 UTC"):
        return [
            {
                "title": "DeWalt Drill",
                "current_bid": "$5.00",
                "est_resale": "$80-$200",
                "url": "https://www.equip-bid.com/auction/123/item/1",
                "auction_id": "123",
                "auction_title": "Test Auction",
                "closing_utc": closing_utc,
            }
        ]

    def test_inserts_one_row_for_future_auction(self):
        from services.notifications import schedule_notifications
        client = self._make_mock_client()
        count = schedule_notifications(client, "user-1", "my-topic", 30, self._make_picks(), [])
        self.assertEqual(count, 1)
        client.table.return_value.insert.assert_called_once()

    def test_skips_auction_where_notify_at_is_in_the_past(self):
        from services.notifications import schedule_notifications
        client = self._make_mock_client()
        count = schedule_notifications(
            client, "user-1", "my-topic", 30,
            self._make_picks(closing_utc="2020-01-01 00:30:00 UTC"), []
        )
        self.assertEqual(count, 0)
        client.table.return_value.insert.assert_not_called()

    def test_returns_zero_when_no_picks(self):
        from services.notifications import schedule_notifications
        client = self._make_mock_client()
        count = schedule_notifications(client, "user-1", "my-topic", 30, [], [])
        self.assertEqual(count, 0)

    def test_groups_flips_and_tools_by_auction(self):
        from services.notifications import schedule_notifications
        client = self._make_mock_client()
        flip = self._make_picks()[0]
        tool = {**flip, "title": "Milwaukee Impact"}
        count = schedule_notifications(client, "user-1", "my-topic", 30, [flip], [tool])
        # Both belong to auction 123 — should produce ONE row
        self.assertEqual(count, 1)
        args = client.table.return_value.insert.call_args[0][0]
        self.assertEqual(len(args), 1)
        self.assertEqual(len(args[0]["items"]), 2)


class TestParseClosingUtc(unittest.TestCase):

    def test_valid_utc_string(self):
        from services.notifications import _parse_closing_utc
        from datetime import timezone
        dt = _parse_closing_utc("2099-12-31 23:00:00 UTC")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(dt.year, 2099)

    def test_none_returns_none(self):
        from services.notifications import _parse_closing_utc
        self.assertIsNone(_parse_closing_utc(None))

    def test_empty_string_returns_none(self):
        from services.notifications import _parse_closing_utc
        self.assertIsNone(_parse_closing_utc(""))

    def test_malformed_string_returns_none(self):
        from services.notifications import _parse_closing_utc
        self.assertIsNone(_parse_closing_utc("not a date"))


if __name__ == "__main__":
    unittest.main()
