# tests/test_scout_utils.py
import sys
import os
import unittest
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from equip_bid_scout import _parse_closing_span
from equip_bid_scout import _save_watchlist_to


def _make_span(title_attr=None, text="5 hours 30 min"):
    """Build a real BeautifulSoup span element for testing."""
    title_html = f' title="{title_attr}"' if title_attr is not None else ""
    html = f"<span{title_html}>{text}</span>"
    return BeautifulSoup(html, "html.parser").find("span")


class TestParseClosingSpan(unittest.TestCase):

    def test_extracts_utc_string_when_valid(self):
        span = _make_span(title_attr="2026-04-22 20:00:00 UTC", text="5 hours 30 min")
        closing, closing_utc = _parse_closing_span(span)
        self.assertEqual(closing_utc, "2026-04-22 20:00:00 UTC")

    def test_display_text_unchanged(self):
        span = _make_span(title_attr="2026-04-22 20:00:00 UTC", text="5 hours 30 min")
        closing, closing_utc = _parse_closing_span(span)
        self.assertEqual(closing, "5 hours 30 min")

    def test_missing_title_returns_none(self):
        span = _make_span(title_attr=None, text="2 hours")
        closing, closing_utc = _parse_closing_span(span)
        self.assertIsNone(closing_utc)

    def test_malformed_title_returns_none(self):
        span = _make_span(title_attr="See auction for UTC details", text="1 hour")
        closing, closing_utc = _parse_closing_span(span)
        self.assertIsNone(closing_utc)

    def test_whitespace_only_title_returns_none(self):
        span = _make_span(title_attr="   ", text="3 hours")
        closing, closing_utc = _parse_closing_span(span)
        self.assertIsNone(closing_utc)

    def test_falls_back_to_display_text_when_title_absent(self):
        span = _make_span(title_attr=None, text="04/24/2026 07:05 pm")
        closing, closing_utc = _parse_closing_span(span)
        self.assertIsNotNone(closing_utc)
        self.assertTrue(closing_utc.endswith(" UTC"), f"Expected UTC suffix, got: {closing_utc}")
        # Verify it parses as a valid datetime
        import datetime
        dt_str = closing_utc.replace(" UTC", "")
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        self.assertIsNotNone(dt)


class TestSaveWatchlist(unittest.TestCase):

    def _make_pick(self, title="DeWalt Drill", bid="$5.00", resale="$80-$200 (brand: dewalt)",
                   closing="5 hours", closing_utc="2026-04-22 20:00:00 UTC",
                   url="https://www.equip-bid.com/auction/123/item/456",
                   auction_id="123", auction_title="Wichita Tools Auction"):
        return {
            "title": title,
            "current_bid": bid,
            "_resale_est": resale,
            "closing": closing,
            "closing_utc": closing_utc,
            "url": url,
            "auction_id": auction_id,
            "auction_title": auction_title,
        }

    def test_watchlist_written_to_disk(self):
        picks = [self._make_pick()]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            _save_watchlist_to(picks, path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn("picks", data)
            self.assertEqual(len(data["picks"]), 1)
        finally:
            os.unlink(path)

    def test_watchlist_fields_mapped_correctly(self):
        picks = [self._make_pick()]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            _save_watchlist_to(picks, path)
            with open(path) as f:
                data = json.load(f)
            p = data["picks"][0]
            self.assertEqual(p["title"], "DeWalt Drill")
            self.assertEqual(p["current_bid"], "$5.00")
            self.assertEqual(p["est_resale"], "$80-$200 (brand: dewalt)")
            self.assertEqual(p["closing_utc"], "2026-04-22 20:00:00 UTC")
            self.assertEqual(p["auction_id"], "123")
            self.assertEqual(p["auction_title"], "Wichita Tools Auction")
            self.assertEqual(p["url"], "https://www.equip-bid.com/auction/123/item/456")
        finally:
            os.unlink(path)

    def test_internal_scoring_keys_not_written(self):
        pick = self._make_pick()
        pick["_pct"] = 0.05
        pick["_ref"] = 140.0
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            _save_watchlist_to([pick], path)
            with open(path) as f:
                data = json.load(f)
            p = data["picks"][0]
            self.assertNotIn("_pct", p)
            self.assertNotIn("_ref", p)
            self.assertNotIn("_resale_est", p)
        finally:
            os.unlink(path)

    def test_empty_picks_writes_valid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            _save_watchlist_to([], path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["picks"], [])
            self.assertIn("generated", data)
        finally:
            os.unlink(path)

    def test_none_closing_utc_written_as_null(self):
        pick = self._make_pick(closing_utc=None)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            _save_watchlist_to([pick], path)
            with open(path) as f:
                data = json.load(f)
            self.assertIsNone(data["picks"][0]["closing_utc"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
