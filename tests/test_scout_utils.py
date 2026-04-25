# tests/test_scout_utils.py
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from services.scout import _parse_closing_span, _clean_pick, _get_ref, parse_dollar, extract_retail, lookup_brand


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
            "_ref": 240.0,
        }

    def test_strips_internal_keys(self):
        result = _clean_pick(self._make_scored_item())
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


class TestGetRef(unittest.TestCase):

    def test_known_brand_returns_midpoint(self):
        item = {"title": "DeWalt 20V MAX Drill Driver Kit"}
        ref = _get_ref(item)
        # dewalt range is (80, 400), midpoint = 240
        self.assertAlmostEqual(ref, 240.0)

    def test_sets_resale_est_on_item(self):
        item = {"title": "DeWalt 20V MAX Drill Driver Kit"}
        _get_ref(item)
        self.assertIn("_resale_est", item)
        self.assertIn("dewalt", item["_resale_est"])

    def test_stated_retail_takes_priority_over_brand(self):
        item = {"title": "DeWalt Drill Retails for $350"}
        ref = _get_ref(item)
        self.assertAlmostEqual(ref, 350.0)
        self.assertIn("stated retail", item["_resale_est"])

    def test_unknown_brand_returns_zero(self):
        item = {"title": "Generic Widget from Store"}
        ref = _get_ref(item)
        self.assertEqual(ref, 0.0)

    def test_high_value_brand_ranks_above_low_value(self):
        macbook = {"title": "MacBook Pro 14 inch"}
        ryobi = {"title": "Ryobi 18V Drill Kit"}
        self.assertGreater(_get_ref(macbook), _get_ref(ryobi))


class TestParseDollar(unittest.TestCase):

    def test_dollar_sign_prefix(self):
        self.assertAlmostEqual(parse_dollar("$5.00"), 5.0)

    def test_no_dollar_sign(self):
        self.assertAlmostEqual(parse_dollar("50"), 50.0)

    def test_with_comma(self):
        self.assertAlmostEqual(parse_dollar("$1,234.00"), 1234.0)

    def test_empty_string_returns_zero(self):
        self.assertAlmostEqual(parse_dollar(""), 0.0)


class TestExtractRetail(unittest.TestCase):

    def test_retails_for_pattern(self):
        self.assertAlmostEqual(extract_retail("Retails for $150"), 150.0)

    def test_msrp_pattern(self):
        self.assertAlmostEqual(extract_retail("MSRP: $200"), 200.0)

    def test_no_retail_returns_none(self):
        self.assertIsNone(extract_retail("DeWalt 20V MAX Drill Driver Kit"))


class TestLookupBrand(unittest.TestCase):

    def test_known_brand(self):
        lo, hi, brand = lookup_brand("DeWalt 20V MAX Drill Driver Kit")
        self.assertEqual(brand, "dewalt")
        self.assertGreater(lo, 0)
        self.assertGreater(hi, lo)

    def test_unknown_brand_returns_zeros(self):
        lo, hi, brand = lookup_brand("Generic Widget from Store")
        self.assertEqual(lo, 0.0)
        self.assertEqual(hi, 0.0)
        self.assertEqual(brand, "")

    def test_case_insensitive(self):
        lo, hi, brand = lookup_brand("MILWAUKEE Impact Driver")
        self.assertEqual(brand, "milwaukee")


if __name__ == "__main__":
    unittest.main()
