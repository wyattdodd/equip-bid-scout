import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestParseClosingUtc(unittest.TestCase):

    def test_parses_valid_utc_string(self):
        from schedule_watches import parse_closing_utc
        dt = parse_closing_utc("2026-04-22 20:00:00 UTC")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 4)
        self.assertEqual(dt.day, 22)
        self.assertEqual(dt.hour, 20)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_returns_none_for_garbage(self):
        from schedule_watches import parse_closing_utc
        self.assertIsNone(parse_closing_utc("not a date"))
        self.assertIsNone(parse_closing_utc(""))
        self.assertIsNone(parse_closing_utc(None))

    def test_trigger_is_30_min_before_close(self):
        from schedule_watches import parse_closing_utc
        closing = parse_closing_utc("2026-04-22 20:00:00 UTC")
        trigger = closing - timedelta(minutes=30)
        self.assertEqual(trigger.hour, 19)
        self.assertEqual(trigger.minute, 30)

    def test_skips_when_trigger_is_in_the_past(self):
        from schedule_watches import parse_closing_utc
        closing = parse_closing_utc("2020-01-01 00:30:00 UTC")
        trigger = closing - timedelta(minutes=30)
        now = datetime.now(timezone.utc)
        self.assertLess(trigger, now)

    def test_parses_local_format(self):
        from schedule_watches import parse_closing_utc
        dt = parse_closing_utc("2026-04-24 19:05:00 LOCAL")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 4)
        self.assertEqual(dt.day, 24)
        self.assertIsNotNone(dt.tzinfo)


class TestRegisterJob(unittest.TestCase):

    def _trigger(self):
        from datetime import datetime, timezone, timedelta
        from schedule_watches import parse_closing_utc
        closing = parse_closing_utc("2099-12-31 20:00:00 UTC")
        return (closing - timedelta(minutes=30)).astimezone()

    def test_returns_true_on_success(self):
        from unittest.mock import patch, MagicMock
        from schedule_watches import register_job
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("schedule_watches.subprocess.run", return_value=mock_result):
            result = register_job("12345", self._trigger())
        self.assertTrue(result)

    def test_returns_false_on_failure(self):
        from unittest.mock import patch, MagicMock
        from schedule_watches import register_job
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "ERROR: Access is denied."
        mock_result.stderr = ""
        with patch("schedule_watches.subprocess.run", return_value=mock_result):
            result = register_job("12345", self._trigger())
        self.assertFalse(result)

    def test_job_name_contains_auction_id(self):
        from unittest.mock import patch, MagicMock
        from schedule_watches import register_job
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("schedule_watches.subprocess.run", return_value=mock_result) as mock_run:
            register_job("99999", self._trigger())
        call_args = mock_run.call_args[0][0]
        self.assertIn("EquipBid-99999", call_args)

    def test_auction_id_quoted_in_command(self):
        from unittest.mock import patch, MagicMock
        from schedule_watches import register_job
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("schedule_watches.subprocess.run", return_value=mock_result) as mock_run:
            register_job("99999", self._trigger())
        call_args = mock_run.call_args[0][0]
        tr_value = call_args[call_args.index("/tr") + 1]
        self.assertIn('"99999"', tr_value)


if __name__ == "__main__":
    unittest.main()
