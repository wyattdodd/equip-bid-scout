# tests/test_scout_utils.py
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from services.scout import _parse_closing_span, _clean_pick, _is_tool


def _make_span(title_attr=None, text="5 hours 30 min"):
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
        import datetime
        dt_str = closing_utc.replace(" UTC", "")
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        self.assertIsNotNone(dt)


class TestCleanPick(unittest.TestCase):

    def _make_scored_item(self):
        return {
            "title": "DeWalt Drill Kit",
            "current_bid": "$5.00",
            "_resale_est": "$80-$200 (brand: dewalt)",
            "closing": "5 hours",
            "closing_utc": "2026-04-22 20:00:00 UTC",
            "url": "https://www.equip-bid.com/auction/123/item/456",
            "auction_id": "123",
            "auction_title": "Wichita Tools",
            "_pct": 0.05,
            "_ref": 140.0,
        }

    def test_strips_internal_scoring_keys(self):
        result = _clean_pick(self._make_scored_item())
        self.assertNotIn("_pct", result)
        self.assertNotIn("_ref", result)
        self.assertNotIn("_resale_est", result)

    def test_maps_resale_est_to_est_resale(self):
        result = _clean_pick(self._make_scored_item())
        self.assertEqual(result["est_resale"], "$80-$200 (brand: dewalt)")

    def test_preserves_required_fields(self):
        result = _clean_pick(self._make_scored_item())
        self.assertEqual(result["title"], "DeWalt Drill Kit")
        self.assertEqual(result["current_bid"], "$5.00")
        self.assertEqual(result["auction_id"], "123")
        self.assertEqual(result["auction_title"], "Wichita Tools")
        self.assertEqual(result["closing_utc"], "2026-04-22 20:00:00 UTC")
        self.assertEqual(result["url"], "https://www.equip-bid.com/auction/123/item/456")

    def test_none_closing_utc_preserved(self):
        item = self._make_scored_item()
        item["closing_utc"] = None
        result = _clean_pick(item)
        self.assertIsNone(result["closing_utc"])


class TestIsTool(unittest.TestCase):

    def test_dewalt_drill_is_tool(self):
        item = {"title": "DeWalt 20V MAX Drill Driver Kit"}
        self.assertTrue(_is_tool(item, ["dewalt", "drill", "milwaukee"]))

    def test_tv_is_not_tool(self):
        item = {"title": "Samsung 65 OLED TV"}
        self.assertFalse(_is_tool(item, ["dewalt", "drill", "milwaukee"]))

    def test_empty_tool_keywords_returns_false(self):
        item = {"title": "DeWalt Drill"}
        self.assertFalse(_is_tool(item, []))

    def test_case_insensitive_match(self):
        item = {"title": "DEWALT Impact Driver"}
        self.assertTrue(_is_tool(item, ["dewalt"]))


if __name__ == "__main__":
    unittest.main()
