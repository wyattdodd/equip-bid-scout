# Equip-Bid Auction Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add phone push notifications (via ntfy.sh) that fire 30 minutes before watched auctions close, triggered by Windows Task Scheduler.

**Architecture:** The scout script gains two additions — capturing the actual UTC closing datetime from HTML and saving `watchlist.json` after displaying results. Two new standalone scripts handle the rest: `schedule_watches.py` registers one Task Scheduler job per auction, and `equip_bid_notify.py` is what Task Scheduler calls at trigger time to send the ntfy.sh push.

**Tech Stack:** Python 3.13 (Windows Store), `requests`, `beautifulsoup4` (already installed), `schtasks` (Windows built-in), ntfy.sh (free HTTP push), `unittest` (built-in, no install needed)

> **Note:** No git repo exists in this project — commit steps are omitted. No pytest — tests use `python -m unittest`.

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `equip_bid_scout.py` | **Modify** | Add `closing_utc` capture + `watchlist.json` save |
| `equip_bid_notify.py` | **Create** | Read watchlist, send ntfy.sh push for one auction |
| `schedule_watches.py` | **Create** | Read watchlist, register Task Scheduler jobs |
| `watchlist.json` | **Generated** | Written by scout, read by notify + schedule scripts |
| `tests/test_scout_utils.py` | **Create** | Unit tests for closing_utc extraction + watchlist save |
| `tests/test_notify.py` | **Create** | Unit tests for notification body building |
| `tests/test_schedule.py` | **Create** | Unit tests for parse_closing_utc + trigger time math |

---

## Task 1: Capture `closing_utc` in the scout

**Files:**
- Modify: `equip_bid_scout.py:276-297` (closing capture + auctions dict)
- Modify: `equip_bid_scout.py:302` (get_auction_items signature)
- Modify: `equip_bid_scout.py:335-340` (items dict)
- Create: `tests/test_scout_utils.py`

The HTML timer span looks like:
```html
<span title="2026-04-22 20:00:00 UTC">5 hours 30 min</span>
```
We read `span["title"]` for scheduling math and `.get_text()` for display (unchanged).

- [ ] **Step 1: Create `tests/test_scout_utils.py` with a failing test**

```python
# tests/test_scout_utils.py
import unittest
from unittest.mock import MagicMock


class TestClosingUtcExtraction(unittest.TestCase):
    """Tests the logic for pulling closing_utc out of the timer span."""

    def _make_span(self, title_attr, display_text):
        span = MagicMock()
        span.get.return_value = title_attr
        span.get_text.return_value = display_text
        return span

    def test_extracts_utc_title_when_present(self):
        span = self._make_span("2026-04-22 20:00:00 UTC", "5 hours 30 min")
        closing_utc = span.get("title", "").strip()
        self.assertEqual(closing_utc, "2026-04-22 20:00:00 UTC")

    def test_display_text_unchanged(self):
        span = self._make_span("2026-04-22 20:00:00 UTC", "5 hours 30 min")
        closing = span.get_text(strip=True)
        self.assertEqual(closing, "5 hours 30 min")

    def test_missing_title_returns_empty(self):
        span = MagicMock()
        span.get.return_value = ""
        closing_utc = span.get("title", "").strip()
        self.assertEqual(closing_utc, "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to confirm it passes (validates our mock approach)**

```
cd "C:\Projects\First Project"
python -m unittest tests/test_scout_utils.py -v
```

Expected output:
```
test_display_text_unchanged ... ok
test_extracts_utc_title_when_present ... ok
test_missing_title_returns_empty ... ok
----------------------------------------------------------------------
Ran 3 tests in 0.XXXs
OK
```

- [ ] **Step 3: Modify `equip_bid_scout.py` — update closing capture (lines 276-282)**

Replace:
```python
        # Closing time — <span title="...UTC..."> inside the timer div
        closing = "Unknown"
        timer_div = row.find("div", class_="auction-listing-timer")
        if timer_div:
            span = timer_div.find("span", title=lambda t: t and "UTC" in t)
            if span:
                closing = span.get_text(strip=True)
```

With:
```python
        # Closing time — display text + UTC datetime from span title attribute
        closing = "Unknown"
        closing_utc = None
        timer_div = row.find("div", class_="auction-listing-timer")
        if timer_div:
            span = timer_div.find("span", title=lambda t: t and "UTC" in t)
            if span:
                closing = span.get_text(strip=True)
                closing_utc = span.get("title", "").strip() or None
```

- [ ] **Step 4: Modify `equip_bid_scout.py` — add `closing_utc` to auctions dict (lines 291-297)**

Replace:
```python
        auctions.append({
            "id": m.group(1),
            "title": title[:90],
            "location": location_text,
            "closing": closing,
            "url": f"{BASE_URL}{href}",
        })
```

With:
```python
        auctions.append({
            "id": m.group(1),
            "title": title[:90],
            "location": location_text,
            "closing": closing,
            "closing_utc": closing_utc,
            "url": f"{BASE_URL}{href}",
        })
```

- [ ] **Step 5: Modify `equip_bid_scout.py` — update `get_auction_items` signature (line 302)**

Replace:
```python
def get_auction_items(auction_id: str, auction_closing: str) -> list[dict]:
    """Scrape all lots from one auction page, pre-filtering by interest keywords."""
```

With:
```python
def get_auction_items(auction_id: str, auction_closing: str, auction_closing_utc: str | None = None) -> list[dict]:
    """Scrape all lots from one auction page, pre-filtering by interest keywords."""
```

- [ ] **Step 6: Modify `equip_bid_scout.py` — add `closing_utc` to items dict (lines 335-340)**

Replace:
```python
        items.append({
            "title": title,
            "current_bid": bid,
            "closing": auction_closing,
            "url": f"{BASE_URL}{href.split('?')[0]}",
        })
```

With:
```python
        items.append({
            "title": title,
            "current_bid": bid,
            "closing": auction_closing,
            "closing_utc": auction_closing_utc,
            "url": f"{BASE_URL}{href.split('?')[0]}",
        })
```

- [ ] **Step 7: Modify `equip_bid_scout.py` — update the `get_auction_items` call in `main()` (line 358)**

Replace:
```python
            items = get_auction_items(a["id"], a["closing"])
            all_items.extend(items)
```

With:
```python
            items = get_auction_items(a["id"], a["closing"], a.get("closing_utc"))
            for item in items:
                item["auction_id"] = a["id"]
                item["auction_title"] = a["title"]
            all_items.extend(items)
```

- [ ] **Step 8: Verify the script still runs without error**

```
cd "C:\Projects\First Project"
python equip_bid_scout.py
```

Expected: Script runs as before, output unchanged. No errors.

---

## Task 2: Save `watchlist.json` after displaying results

**Files:**
- Modify: `equip_bid_scout.py` (add `import json`, `WATCHLIST_PATH`, `save_watchlist()`, call in `main()`)
- Modify: `tests/test_scout_utils.py` (add watchlist save tests)

- [ ] **Step 1: Add watchlist save tests to `tests/test_scout_utils.py`**

Add this class after the existing `TestClosingUtcExtraction` class:

```python
import json
import os
import tempfile


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
```

Also add this import at the top of the test file (after the existing imports):
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from equip_bid_scout import _save_watchlist_to
```

- [ ] **Step 2: Run tests — expect ImportError (function doesn't exist yet)**

```
cd "C:\Projects\First Project"
python -m unittest tests/test_scout_utils.py -v
```

Expected: `ImportError: cannot import name '_save_watchlist_to'` — confirms TDD red state.

- [ ] **Step 3: Add `import json` to `equip_bid_scout.py` (line 15, after `import re`)**

Replace:
```python
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
```

With:
```python
import json
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
```

- [ ] **Step 4: Add `WATCHLIST_PATH` to the config block in `equip_bid_scout.py` (after `TOP_N = 5` on line 34)**

Replace:
```python
MAX_AUCTIONS = 10   # Auctions to scan per run
TOP_N = 5           # Final picks returned
# ──────────────────────────────────────────────────────────────────────────────
```

With:
```python
MAX_AUCTIONS = 10   # Auctions to scan per run
TOP_N = 5           # Final picks returned
WATCHLIST_PATH = "watchlist.json"
# ──────────────────────────────────────────────────────────────────────────────
```

- [ ] **Step 5: Add `_save_watchlist_to()` and `save_watchlist()` to `equip_bid_scout.py` — insert just before the `parse_dollar` function (before line 170)**

```python
def _save_watchlist_to(picks: list[dict], path: str) -> None:
    """Write picks to a watchlist JSON file, stripping internal scoring keys."""
    import datetime
    clean = []
    for p in picks:
        clean.append({
            "title":         p.get("title", ""),
            "current_bid":   p.get("current_bid", "$0.00"),
            "est_resale":    p.get("_resale_est", "Unknown"),
            "closing":       p.get("closing", "Unknown"),
            "closing_utc":   p.get("closing_utc"),
            "url":           p.get("url", ""),
            "auction_id":    p.get("auction_id", ""),
            "auction_title": p.get("auction_title", ""),
        })
    data = {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "picks": clean,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_watchlist(picks: list[dict]) -> None:
    _save_watchlist_to(picks, WATCHLIST_PATH)

```

- [ ] **Step 6: Call `save_watchlist()` in `main()` — add after the closing `print("=" * 68)` line (after line 413)**

Replace:
```python
    print("\n" + "=" * 68)


if __name__ == "__main__":
    main()
```

With:
```python
    print("\n" + "=" * 68)

    save_watchlist(picks)
    print(f"\nWatchlist saved to {WATCHLIST_PATH}")
    print("Run 'py schedule_watches.py' to set phone alerts for these picks.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run tests — all should pass**

```
cd "C:\Projects\First Project"
python -m unittest tests/test_scout_utils.py -v
```

Expected:
```
test_display_text_unchanged ... ok
test_extracts_utc_title_when_present ... ok
test_missing_title_returns_empty ... ok
test_internal_scoring_keys_not_written ... ok
test_watchlist_fields_mapped_correctly ... ok
test_watchlist_written_to_disk ... ok
----------------------------------------------------------------------
Ran 6 tests in 0.XXXs
OK
```

- [ ] **Step 8: Smoke test — run the scout and verify `watchlist.json` is created**

```
cd "C:\Projects\First Project"
python equip_bid_scout.py
```

Expected: Same output as before, then:
```
Watchlist saved to watchlist.json
Run 'py schedule_watches.py' to set phone alerts for these picks.
```

Verify the file exists and looks correct:
```
python -c "import json; d=json.load(open('watchlist.json')); print(json.dumps(d, indent=2))"
```

Expected: A JSON object with `"generated"` and `"picks"` array. Each pick should have `auction_id`, `closing_utc`, and `est_resale` fields.

---

## Task 3: Create `equip_bid_notify.py`

**Files:**
- Create: `equip_bid_notify.py`
- Create: `tests/test_notify.py`

This script is called by Task Scheduler with `--auction {auction_id}`. It reads `watchlist.json`, finds all picks for that auction, builds a notification body, and POSTs to ntfy.sh.

- [ ] **Step 1: Create `tests/test_notify.py` with failing tests**

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — expect ImportError**

```
cd "C:\Projects\First Project"
python -m unittest tests/test_notify.py -v
```

Expected: `ImportError: No module named 'equip_bid_notify'`

- [ ] **Step 3: Create `equip_bid_notify.py`**

```python
#!/usr/bin/env python3
"""
equip_bid_notify.py
Called by Windows Task Scheduler 30 minutes before a watched auction closes.
Reads watchlist.json, groups picks by auction, sends ntfy.sh push notification.

Usage:
    py equip_bid_notify.py --auction {auction_id}

Requires:
    pip install requests
"""

import argparse
import json
import sys
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
NTFY_TOPIC     = "equip-bid-wichita"   # subscribe to this in the ntfy app
WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"
BASE_URL       = "https://www.equip-bid.com"
# ──────────────────────────────────────────────────────────────────────────────


def build_notification_body(auction_id: str, picks: list[dict]) -> str:
    """Build the push notification body string for one auction's picks."""
    if not picks:
        raise ValueError(f"No picks provided for auction {auction_id}")

    auction_title = picks[0].get("auction_title", f"Auction {auction_id}")
    auction_url = f"{BASE_URL}/auction/{auction_id}"

    lines = [f"Auction: {auction_title}"]
    for p in picks:
        title = p["title"][:60]
        bid = p.get("current_bid", "?")
        resale = p.get("est_resale", "?")
        lines.append(f"• {title}  |  Bid: {bid}  |  Est: {resale}")
    lines.append(auction_url)

    return "\n".join(lines)


def send_notification(topic: str, body: str) -> None:
    """POST notification to ntfy.sh."""
    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": "⏰ Equip-Bid — 30 min left",
            "Priority": "high",
            "Tags": "bell",
        },
        timeout=10,
    )
    resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser(
        description="Send ntfy.sh alert for a watched auction closing soon."
    )
    parser.add_argument("--auction", required=True, help="Auction ID to notify for")
    args = parser.parse_args()
    auction_id = args.auction

    if not WATCHLIST_PATH.exists():
        print(f"[ERROR] watchlist.json not found at {WATCHLIST_PATH}")
        print("Run equip_bid_scout.py to generate it.")
        sys.exit(1)

    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)

    picks = [p for p in data.get("picks", []) if p.get("auction_id") == auction_id]

    if not picks:
        print(f"[WARN] No picks found for auction {auction_id} in watchlist — nothing sent")
        sys.exit(0)

    body = build_notification_body(auction_id, picks)

    try:
        send_notification(NTFY_TOPIC, body)
        print(f"[OK] Notification sent for auction {auction_id} ({len(picks)} item(s))")
    except Exception as e:
        print(f"[ERROR] ntfy.sh POST failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — all should pass**

```
cd "C:\Projects\First Project"
python -m unittest tests/test_notify.py -v
```

Expected:
```
test_body_contains_auction_title ... ok
test_body_contains_auction_url ... ok
test_body_contains_bids ... ok
test_body_contains_item_titles ... ok
test_empty_picks_raises ... ok
----------------------------------------------------------------------
Ran 5 tests in 0.XXXs
OK
```

- [ ] **Step 5: ntfy.sh app setup on phone (one-time)**

1. Install the **ntfy** app from App Store or Google Play
2. Tap **+** → **Subscribe to topic**
3. Enter: `equip-bid-wichita` (or whatever you set `NTFY_TOPIC` to)
4. Tap Subscribe

- [ ] **Step 6: Smoke test — manually trigger a notification**

First, make sure `watchlist.json` exists from the scout smoke test in Task 2. Then grab any `auction_id` from it:

```
python -c "import json; d=json.load(open('watchlist.json')); print(d['picks'][0]['auction_id'])"
```

Then fire it:
```
cd "C:\Projects\First Project"
python equip_bid_notify.py --auction {the_auction_id_you_just_printed}
```

Expected terminal output:
```
[OK] Notification sent for auction 12345 (2 item(s))
```

Expected on your phone: push notification titled "⏰ Equip-Bid — 30 min left" listing the items.

---

## Task 4: Create `schedule_watches.py`

**Files:**
- Create: `schedule_watches.py`
- Create: `tests/test_schedule.py`

This script reads `watchlist.json`, deduplicates by `auction_id`, and registers one `schtasks` job per auction timed at `closing_utc − 30 minutes`. Uses absolute paths so Task Scheduler can find the files regardless of working directory.

- [ ] **Step 1: Create `tests/test_schedule.py` with failing tests**

```python
# tests/test_schedule.py
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
        # A time far in the past
        closing = parse_closing_utc("2020-01-01 00:30:00 UTC")
        trigger = closing - timedelta(minutes=30)
        now = datetime.now(timezone.utc)
        self.assertLess(trigger, now)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — expect ImportError**

```
cd "C:\Projects\First Project"
python -m unittest tests/test_schedule.py -v
```

Expected: `ImportError: No module named 'schedule_watches'`

- [ ] **Step 3: Create `schedule_watches.py`**

```python
#!/usr/bin/env python3
"""
schedule_watches.py
Reads watchlist.json and registers Windows Task Scheduler jobs to fire
equip_bid_notify.py 30 minutes before each watched auction closes.

Usage:
    py schedule_watches.py

Run after equip_bid_scout.py. Safe to re-run — existing jobs are overwritten.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"
NOTIFY_SCRIPT  = Path(__file__).parent / "equip_bid_notify.py"
PYTHON_EXE     = sys.executable   # full path to python3.13.exe
# ──────────────────────────────────────────────────────────────────────────────


def parse_closing_utc(utc_str: str | None) -> datetime | None:
    """Parse 'YYYY-MM-DD HH:MM:SS UTC' into a UTC-aware datetime. Returns None on failure."""
    if not utc_str:
        return None
    try:
        clean = utc_str.replace(" UTC", "").strip()
        dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def register_job(auction_id: str, trigger_local: datetime) -> bool:
    """Register a one-time Task Scheduler job. Returns True on success."""
    job_name  = f"EquipBid-{auction_id}"
    date_str  = trigger_local.strftime("%m/%d/%Y")
    time_str  = trigger_local.strftime("%H:%M")
    command   = f'"{PYTHON_EXE}" "{NOTIFY_SCRIPT}" --auction {auction_id}'

    result = subprocess.run(
        [
            "schtasks", "/create",
            "/tn", job_name,
            "/tr", command,
            "/sc", "once",
            "/sd", date_str,
            "/st", time_str,
            "/f",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def main():
    if not WATCHLIST_PATH.exists():
        print(f"[ERROR] watchlist.json not found at {WATCHLIST_PATH}")
        print("Run equip_bid_scout.py first.")
        sys.exit(1)

    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)

    picks = data.get("picks", [])
    if not picks:
        print("No picks in watchlist. Run equip_bid_scout.py first.")
        sys.exit(0)

    now = datetime.now(timezone.utc)
    seen_auctions: set[str] = set()
    scheduled = 0
    skipped = 0

    for pick in picks:
        auction_id = pick.get("auction_id", "")
        if not auction_id or auction_id in seen_auctions:
            continue
        seen_auctions.add(auction_id)

        closing_dt = parse_closing_utc(pick.get("closing_utc"))
        if not closing_dt:
            print(f"  [SKIP] No valid closing time for auction {auction_id} — '{pick['title'][:50]}'")
            skipped += 1
            continue

        trigger_dt = closing_dt - timedelta(minutes=30)

        if trigger_dt <= now:
            minutes_left = int((closing_dt - now).total_seconds() / 60)
            print(f"  [SKIP] Auction {auction_id} closes in ~{minutes_left} min — too late to schedule")
            skipped += 1
            continue

        trigger_local = trigger_dt.astimezone()
        auction_title = pick.get("auction_title", auction_id)

        if register_job(auction_id, trigger_local):
            time_display = trigger_local.strftime("%I:%M %p")
            print(f"  [OK] EquipBid-{auction_id} → alert at {time_display}  ({auction_title[:50]})")
            scheduled += 1
        else:
            print(f"  [ERROR] schtasks failed for auction {auction_id}")
            skipped += 1

    print(f"\n{scheduled} job(s) scheduled, {skipped} skipped.")
    if scheduled > 0:
        print("View or delete jobs: open Task Scheduler → Task Scheduler Library → search 'EquipBid'")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — all should pass**

```
cd "C:\Projects\First Project"
python -m unittest tests/test_schedule.py -v
```

Expected:
```
test_parses_valid_utc_string ... ok
test_returns_none_for_garbage ... ok
test_skips_when_trigger_is_in_the_past ... ok
test_trigger_is_30_min_before_close ... ok
----------------------------------------------------------------------
Ran 4 tests in 0.XXXs
OK
```

- [ ] **Step 5: Run all tests together to confirm nothing broke**

```
cd "C:\Projects\First Project"
python -m unittest discover -s tests -v
```

Expected: All 15 tests pass with no errors.

- [ ] **Step 6: Smoke test — run `schedule_watches.py` against the real watchlist**

```
cd "C:\Projects\First Project"
python schedule_watches.py
```

Expected (if auctions close more than 30 min from now):
```
  [OK] EquipBid-12345 → alert at 02:30 PM  (Wichita Industrial Tools)
  [OK] EquipBid-12346 → alert at 04:15 PM  (...)

2 job(s) scheduled, 0 skipped.
View or delete jobs: open Task Scheduler → Task Scheduler Library → search 'EquipBid'
```

- [ ] **Step 7: Verify jobs appear in Task Scheduler**

Open **Task Scheduler** (search in Start menu) → **Task Scheduler Library** → look for entries named `EquipBid-{id}`. Each should show the correct trigger time and point to your Python executable.

---

## End-to-End Verification

After all tasks complete, run through the full workflow:

1. `python equip_bid_scout.py` → see picks, confirm `watchlist.json` written
2. `python schedule_watches.py` → confirm jobs registered in Task Scheduler
3. Manually test the notification: `python equip_bid_notify.py --auction {id}` → confirm push arrives on phone
4. Wait for a naturally-scheduled trigger (or create a test job 2 minutes in the future) to confirm Task Scheduler fires correctly
