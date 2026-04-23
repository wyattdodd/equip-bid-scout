# Streamlit + Supabase Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the local CLI equip-bid scout into a multi-user Streamlit web app with Supabase auth/database and GitHub Actions–powered ntfy.sh push notifications.

**Architecture:** Streamlit Cloud hosts the UI; Supabase handles auth and stores per-user settings, run history, and scheduled notifications; a GitHub Actions cron runs `scripts/dispatcher.py` every 15 minutes to fire ntfy.sh pushes for due rows — no PC required. The scout's scraping and scoring logic moves to `services/scout.py` unchanged; only config is parameterized.

**Tech Stack:** Python 3.13, `streamlit>=1.31.0`, `supabase>=2.0.0`, `requests`, `beautifulsoup4`, `python -m unittest` (built-in)

**Spec:** `docs/superpowers/specs/2026-04-23-streamlit-supabase-rebuild-design.md`

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `streamlit_app.py` | **Create** | Login/signup/logout gate; session state management |
| `pages/1_Dashboard.py` | **Create** | Last run summary + upcoming notification list |
| `pages/2_Settings.py` | **Create** | Per-user settings form; upsert to Supabase |
| `pages/3_Run_Tool.py` | **Create** | Run scout; display results; write DB rows |
| `services/__init__.py` | **Create** | Empty — marks services as a package |
| `services/supabase_client.py` | **Create** | Client factory + `require_auth()` guard |
| `services/scout.py` | **Create** | Refactored `equip_bid_scout.py`; accepts user settings as params |
| `services/notifications.py` | **Create** | `build_ntfy_body()` + `schedule_notifications()` |
| `scripts/__init__.py` | **Create** | Empty — marks scripts as a package |
| `scripts/dispatcher.py` | **Create** | GitHub Actions runner: read Supabase, fire ntfy.sh |
| `.github/workflows/notify_dispatcher.yml` | **Create** | Cron workflow triggering dispatcher |
| `tests/test_scout_utils.py` | **Modify** | Update imports; replace `TestSaveWatchlist` with `TestCleanPick` + `TestIsTool` |
| `tests/test_notifications.py` | **Create** | Tests for `build_ntfy_body` and `schedule_notifications` |
| `tests/test_dispatcher.py` | **Create** | Tests for dispatcher's `build_ntfy_body` and `post_ntfy` |
| `requirements.txt` | **Create** | All dependencies for Streamlit Cloud |
| `.streamlit/secrets.toml` | **Create** | Template only — gitignored |
| `equip_bid_scout.py` | **Delete** | Replaced by `services/scout.py` |
| `equip_bid_check.py` | **Delete** | Replaced by `scripts/dispatcher.py` |
| `main.py` | **Delete** | Replaced by `pages/3_Run_Tool.py` |
| `tests/test_check.py` | **Delete** | Tested `equip_bid_check.py` which is removed |

---

## Task 1: Project scaffold and cleanup

**Files:**
- Create: `requirements.txt`, `services/__init__.py`, `scripts/__init__.py`, `.streamlit/secrets.toml`
- Modify: `.gitignore`
- Delete: `equip_bid_scout.py`, `equip_bid_check.py`, `main.py`, `tests/test_check.py`

- [ ] **Step 1: Create `requirements.txt`**

```
streamlit>=1.31.0
supabase>=2.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
```

- [ ] **Step 2: Create package init files**

Create `services/__init__.py` — empty file.
Create `scripts/__init__.py` — empty file.

- [ ] **Step 3: Create `.streamlit/secrets.toml` template**

```toml
# Copy this file to .streamlit/secrets.toml and fill in your values.
# NEVER commit secrets.toml to git.
SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_KEY = "your-anon-public-key-here"
```

- [ ] **Step 4: Update `.gitignore`**

Add these lines if not already present:

```
.streamlit/secrets.toml
__pycache__/
*.pyc
.env
```

- [ ] **Step 5: Stop tracking `watchlist.json` in git**

```bash
git rm --cached watchlist.json
```

Add `watchlist.json` to `.gitignore`.

- [ ] **Step 6: Delete old files**

```bash
rm equip_bid_scout.py equip_bid_check.py main.py tests/test_check.py
```

Also delete `equip_bid_notify.py` and `schedule_watches.py` if they exist.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold Streamlit project structure, remove old CLI files"
```

---

## Task 2: Supabase project setup (manual steps)

**No code — all steps are done in the Supabase dashboard at supabase.com.**

- [ ] **Step 1: Create a new Supabase project**

Go to https://supabase.com → New project. Note down:
- Project URL (looks like `https://abcdefgh.supabase.co`)
- Anon public key (under Project Settings → API → `anon public`)
- Service role key (under Project Settings → API → `service_role` — keep this secret)

- [ ] **Step 2: Run the schema SQL**

In Supabase → SQL Editor → New query, paste and run:

```sql
CREATE TABLE user_settings (
  user_id           uuid        PRIMARY KEY REFERENCES auth.users(id),
  city              text        DEFAULT 'wichita',
  interest_keywords text[]      DEFAULT '{}',
  tool_keywords     text[]      DEFAULT '{}',
  ntfy_topic        text,
  notify_minutes    integer     DEFAULT 30,
  updated_at        timestamptz DEFAULT now()
);

CREATE TABLE watchlist_runs (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        REFERENCES auth.users(id),
  generated_at timestamptz DEFAULT now(),
  flips        jsonb       DEFAULT '[]',
  tools        jsonb       DEFAULT '[]'
);

CREATE TABLE scheduled_notifications (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid        REFERENCES auth.users(id),
  auction_id    text        NOT NULL,
  auction_title text,
  ntfy_topic    text        NOT NULL,
  notify_at     timestamptz NOT NULL,
  notified      boolean     DEFAULT false,
  notified_at   timestamptz,
  items         jsonb       NOT NULL,
  created_at    timestamptz DEFAULT now()
);
```

- [ ] **Step 3: Enable RLS and create policies**

In Supabase → SQL Editor → New query, paste and run:

```sql
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_rows" ON user_settings
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE watchlist_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_rows" ON watchlist_runs
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE scheduled_notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_rows" ON scheduled_notifications
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
```

- [ ] **Step 4: Configure auth settings**

In Supabase → Authentication → Email:
- Set "Confirm email" to **disabled** (so users can log in immediately without email verification — you're manually onboarding each user anyway)
- Leave all other defaults

- [ ] **Step 5: Verify tables exist**

In Supabase → Table Editor, confirm `user_settings`, `watchlist_runs`, and `scheduled_notifications` are all visible.

---

## Task 3: `services/supabase_client.py`

**Files:**
- Create: `services/supabase_client.py`

- [ ] **Step 1: Create `services/supabase_client.py`**

```python
import streamlit as st
from supabase import create_client, Client


def get_client() -> Client:
    client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
    return client


def require_auth() -> str:
    """Returns user_id if authenticated, otherwise stops page rendering."""
    if not st.session_state.get("access_token"):
        st.warning("Please log in to continue.")
        st.page_link("streamlit_app.py", label="Go to Login →")
        st.stop()
    return st.session_state["user_id"]
```

- [ ] **Step 2: Populate `.streamlit/secrets.toml` with your Supabase values**

```toml
SUPABASE_URL = "https://your-actual-project-ref.supabase.co"
SUPABASE_KEY = "your-actual-anon-key"
```

- [ ] **Step 3: Verify the module imports cleanly**

```bash
cd "C:\Projects\First Project"
python -c "import services.supabase_client; print('Module imports OK')"
```

Expected: `Module imports OK`

If you see `ModuleNotFoundError: No module named 'supabase'`, run `pip install supabase` first. Live Supabase connection is verified in Task 6 smoke test.

- [ ] **Step 4: Commit**

```bash
git add services/__init__.py services/supabase_client.py .streamlit/secrets.toml
git commit -m "feat: add Supabase client factory and auth guard"
```

---

## Task 4: `services/scout.py`

**Files:**
- Create: `services/scout.py`
- Modify: `tests/test_scout_utils.py`

- [ ] **Step 1: Update `tests/test_scout_utils.py` — fix imports and replace `TestSaveWatchlist`**

Replace the entire file contents with:

```python
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
```

- [ ] **Step 2: Run tests — expect ImportError (services/scout.py doesn't exist yet)**

```bash
cd "C:\Projects\First Project"
python -m unittest tests/test_scout_utils.py -v 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'services.scout'`

- [ ] **Step 3: Create `services/scout.py`**

```python
#!/usr/bin/env python3
"""
services/scout.py
Scrapes equip-bid.com and scores items by arbitrage potential.
All per-user config (city, keywords) is passed as parameters — no hardcoded values.
"""

import datetime
import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.equip-bid.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$")
_LOCAL_FMT = "%m/%d/%Y %I:%M %p"

MAX_AUCTIONS = 10
TOP_FLIPS = 5
TOP_TOOLS = 5
MIN_RESALE_VALUE = 75.0

EXCLUSION_PHRASES = [
    "case for", "case compatible", "compatible with", "replacement for",
    "adapter for", "charger for", "screen protector", "tempered glass",
    "silicone case", "phone case", "tablet case",
    "carrying case", "travel case", "hard case", "protective case",
    "cover for", "stand for", "holder for", "mount for",
    "laptop case", "laptop bag", "laptop backpack", "laptop sleeve",
    "laptop stand", "laptop riser", "laptop desk",
    "couch cover", "sofa cover", "chair cover", "sectional cover",
    "slipcover", "slip cover", "furniture cover", "cushion cover",
    "cushion replacement", "upholstery foam",
    "backup camera", "rear camera", "reverse camera", "dash cam",
    "baby camera", "baby monitor", "car camera", "parking camera",
    "camera strap", "camera bag", "lens cap",
    "headphone stand", "speaker stand", "earbud tips",
    "actuator", "rmt motor", "lift motor",
    "replacement legs", "furniture legs", "sofa legs", "couch legs",
    "rv seat", "seat cover", "outdoor cushion", "chair cushion",
    "patio cushion", "cushion set", "cushion replacement",
    "missing", "parts only", "for parts", "not working", "as is",
    "damaged", "cracked screen",
]

BRAND_VALUE = {
    "dewalt":               (80,   400),
    "milwaukee":            (100,  500),
    "makita":               (80,   350),
    "bosch":                (60,   300),
    "ridgid":               (60,   250),
    "ryobi":                (40,   200),
    "craftsman":            (30,   150),
    "black+decker":         (25,   120),
    "worx":                 (25,   100),
    "macbook":              (400, 1200),
    "ipad":                 (200,  800),
    "iphone":               (250,  900),
    "airpod":               (80,   250),
    "apple watch":          (150,  400),
    "bose":                 (100,  400),
    "beats":                (80,   300),
    "sony":                 (50,   350),
    "jbl":                  (40,   200),
    "sonos":                (150,  600),
    "oled":                 (400, 1800),
    "qled":                 (200, 1200),
    "television":           (100,  700),
    "playstation 5":        (350,  500),
    "ps5":                  (350,  500),
    "xbox series":          (250,  450),
    "nintendo switch":      (150,  300),
    "laptop":               (150,  700),
    "chromebook":           (80,   300),
    "dslr":                 (200, 1500),
    "mirrorless":           (300, 2000),
    "action camera":        (80,   400),
    "4k camera":            (100,  600),
    "drone":                (100,  600),
    "gopro":                (100,  400),
    "headphone":            (40,   300),
    "subwoofer":            (80,   500),
    "soundbar":             (80,   400),
    "receiver":             (80,   500),
    "amplifier":            (80,   600),
    "restoration hardware": (500, 3000),
    "pottery barn":         (200, 1200),
    "west elm":             (150,  900),
    "la-z-boy":             (200,  900),
    "lazboy":               (200,  900),
    "natuzzi":              (600, 2500),
    "ethan allen":          (300, 1800),
    "ashley":               (100,  600),
    "sectional":            (250, 1200),
    "recliner":             (120,  600),
    "dresser":              (100,  500),
    "bookcase":             (60,   350),
    "compressor":           (100,  600),
    "welder":               (120,  700),
    "generator":            (200, 1500),
}


def parse_dollar(text: str) -> float:
    m = re.search(r"\$?([\d,]+(?:\.\d+)?)", text.replace(",", ""))
    return float(m.group(1)) if m else 0.0


def extract_retail(title: str) -> float | None:
    patterns = [
        r"retail[s]?\s+for\s+\$?([\d,]+)",
        r"retail(?:s)?\s*:?\s*\$?([\d,]+)",
        r"msrp\s*:?\s*\$?([\d,]+)",
    ]
    for p in patterns:
        m = re.search(p, title, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def lookup_brand(title: str) -> tuple[float, float, str]:
    t = title.lower()
    for brand, (lo, hi) in BRAND_VALUE.items():
        if brand in t:
            return lo, hi, brand
    return 0.0, 0.0, ""


def score_item(item: dict) -> float:
    bid = parse_dollar(item["current_bid"])
    title = item["title"]

    retail = extract_retail(title)
    lo_resale, hi_resale, brand = lookup_brand(title)

    if retail and retail > 0:
        if retail < MIN_RESALE_VALUE:
            return 0.0
        ref = retail
        item["_resale_est"] = f"~${retail:.0f} (stated retail)"
    elif lo_resale > 0:
        ref = (lo_resale + hi_resale) / 2
        item["_resale_est"] = f"${lo_resale:.0f}-${hi_resale:.0f} (brand: {brand})"
    else:
        return 0.0

    if ref < MIN_RESALE_VALUE:
        return 0.0

    effective_bid = bid if bid > 0 else 1.0
    pct = effective_bid / ref
    item["_pct"] = pct
    item["_ref"] = ref

    if pct >= 0.70:
        return 0.0

    base = (1.0 - pct) * 100
    if bid == 0:
        base += 25
    if pct < 0.20:
        base += 20

    return base


def _parse_closing_span(span) -> tuple[str, str | None]:
    closing = span.get_text(strip=True)
    raw = span.get("title", "").strip()
    if _UTC_RE.match(raw):
        return closing, raw
    try:
        dt = datetime.datetime.strptime(closing, _LOCAL_FMT)
        local_tz = datetime.datetime.now().astimezone().tzinfo
        dt_utc = dt.replace(tzinfo=local_tz).astimezone(datetime.timezone.utc)
        return closing, dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return closing, None


def _clean_pick(p: dict) -> dict:
    return {
        "title":         p.get("title", ""),
        "current_bid":   p.get("current_bid", "$0.00"),
        "est_resale":    p.get("_resale_est", "Unknown"),
        "closing":       p.get("closing", "Unknown"),
        "closing_utc":   p.get("closing_utc"),
        "url":           p.get("url", ""),
        "auction_id":    p.get("auction_id", ""),
        "auction_title": p.get("auction_title", ""),
    }


def _is_tool(item: dict, tool_keywords: list[str]) -> bool:
    t = item["title"].lower()
    return any(kw in t for kw in tool_keywords)


def get_nearby_auctions(city_filter: list[str]) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/auction/list", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    auctions = []
    for title_span in soup.select("span.auction-title.description-wrap-fix"):
        link = title_span.find("a")
        if not link:
            continue
        href = link.get("href", "")
        title = link.get_text(strip=True)

        row = title_span
        for _ in range(6):
            row = row.parent
            if row and "row" in (row.get("class") or []):
                break

        location_text = ""
        for i_tag in row.find_all("i"):
            if "globe" in " ".join(i_tag.get("class") or []):
                location_text = i_tag.parent.get_text(strip=True)
                break

        closing = "Unknown"
        closing_utc = None
        timer_div = row.find("div", class_="auction-listing-timer")
        if timer_div:
            span = timer_div.find("span", title=lambda t: t and "UTC" in t)
            if span:
                closing, closing_utc = _parse_closing_span(span)

        if not any(kw in location_text.lower() for kw in city_filter):
            continue

        m = re.search(r"/auction/(\d+)", href)
        if not m:
            continue

        auctions.append({
            "id": m.group(1),
            "title": title[:90],
            "location": location_text,
            "closing": closing,
            "closing_utc": closing_utc,
            "url": f"{BASE_URL}{href}",
        })

    return auctions[:MAX_AUCTIONS]


def get_auction_items(
    auction_id: str,
    auction_closing: str,
    interest_keywords: list[str],
    auction_closing_utc: str | None = None,
) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/auction/{auction_id}", headers=HEADERS, timeout=20
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    for h4 in soup.find_all("h4", id=lambda x: x and x.startswith("itemTitle")):
        link = h4.find("a")
        if not link:
            continue

        title = link.get_text(strip=True)
        href = link.get("href", "")
        title_lower = title.lower()

        if not any(kw in title_lower for kw in interest_keywords):
            continue
        if any(ex in title_lower for ex in EXCLUSION_PHRASES):
            continue

        internal_id = h4["id"].replace("itemTitle", "")
        bid_span = soup.find(
            "span",
            id=f"lot_current_bid_lot_equip-bid_{auction_id}_{internal_id}",
        )
        bid = bid_span.get_text(strip=True) if bid_span else "$0.00"

        items.append({
            "title": title,
            "current_bid": bid,
            "closing": auction_closing,
            "closing_utc": auction_closing_utc,
            "url": f"{BASE_URL}{href.split('?')[0]}",
        })

    return items


def run_scout(
    city_filter: list[str],
    interest_keywords: list[str],
    tool_keywords: list[str],
) -> dict:
    """Scrape and score equip-bid.com using per-user config. Returns {"flips": [...], "tools": [...]}."""
    auctions = get_nearby_auctions(city_filter)
    if not auctions:
        return {"flips": [], "tools": []}

    all_items: list[dict] = []
    for a in auctions:
        try:
            items = get_auction_items(a["id"], a["closing"], interest_keywords, a.get("closing_utc"))
            for item in items:
                item["auction_id"] = a["id"]
                item["auction_title"] = a["title"]
            all_items.extend(items)
            time.sleep(0.5)
        except Exception:
            pass

    scored = []
    for item in all_items:
        s = score_item(item)
        if s > 0:
            scored.append((s, item))
    scored.sort(key=lambda x: x[0], reverse=True)

    tool_scored = [(s, it) for s, it in scored if _is_tool(it, tool_keywords)]
    flip_scored = [(s, it) for s, it in scored if not _is_tool(it, tool_keywords)]

    return {
        "flips": [_clean_pick(it) for _, it in flip_scored[:TOP_FLIPS]],
        "tools": [_clean_pick(it) for _, it in tool_scored[:TOP_TOOLS]],
    }
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd "C:\Projects\First Project"
python -m unittest tests/test_scout_utils.py -v
```

Expected output:
```
test_case_insensitive_match ... ok
test_dewalt_drill_is_tool ... ok
test_empty_tool_keywords_returns_false ... ok
test_tv_is_not_tool ... ok
test_display_text_unchanged ... ok
test_extracts_utc_string_when_valid ... ok
test_falls_back_to_display_text_when_title_absent ... ok
test_malformed_title_returns_none ... ok
test_missing_title_returns_none ... ok
test_whitespace_only_title_returns_none ... ok
test_maps_resale_est_to_est_resale ... ok
test_none_closing_utc_preserved ... ok
test_preserves_required_fields ... ok
test_strips_internal_scoring_keys ... ok
----------------------------------------------------------------------
Ran 14 tests in 0.XXXs
OK
```

- [ ] **Step 5: Commit**

```bash
git add services/scout.py tests/test_scout_utils.py
git commit -m "feat: add services/scout.py refactored from equip_bid_scout.py"
```

---

## Task 5: `services/notifications.py`

**Files:**
- Create: `services/notifications.py`
- Create: `tests/test_notifications.py`

- [ ] **Step 1: Create `tests/test_notifications.py` with failing tests**

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd "C:\Projects\First Project"
python -m unittest tests/test_notifications.py -v 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'services.notifications'`

- [ ] **Step 3: Create `services/notifications.py`**

```python
from datetime import datetime, timezone, timedelta

BASE_URL = "https://www.equip-bid.com"


def _parse_closing_utc(utc_str: str | None) -> datetime | None:
    if not utc_str:
        return None
    try:
        clean = utc_str.replace(" UTC", "").strip()
        dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_ntfy_body(auction_id: str, items: list[dict]) -> str:
    if not items:
        raise ValueError(f"No items for auction {auction_id}")
    auction_title = items[0].get("auction_title", f"Auction {auction_id}")
    lines = [f"Auction: {auction_title}"]
    for item in items:
        title = item.get("title", "")[:60]
        bid = item.get("current_bid", "?")
        resale = item.get("est_resale", "?")
        lines.append(f"• {title}  |  Bid: {bid}  |  Est: {resale}")
    lines.append(f"{BASE_URL}/auction/{auction_id}")
    return "\n".join(lines)


def schedule_notifications(
    supabase_client,
    user_id: str,
    ntfy_topic: str,
    notify_minutes: int,
    flips: list[dict],
    tools: list[dict],
) -> int:
    supabase_client.table("scheduled_notifications")\
        .delete()\
        .eq("user_id", user_id)\
        .eq("notified", False)\
        .execute()

    all_picks = flips + tools
    if not all_picks:
        return 0

    auctions: dict[str, list[dict]] = {}
    for pick in all_picks:
        aid = pick.get("auction_id", "")
        if aid:
            auctions.setdefault(aid, []).append(pick)

    now = datetime.now(timezone.utc)
    rows = []

    for auction_id, picks in auctions.items():
        closing_dt = _parse_closing_utc(picks[0].get("closing_utc"))
        if not closing_dt:
            continue
        notify_at = closing_dt - timedelta(minutes=notify_minutes)
        if notify_at <= now:
            continue

        rows.append({
            "user_id": user_id,
            "auction_id": auction_id,
            "auction_title": picks[0].get("auction_title", ""),
            "ntfy_topic": ntfy_topic,
            "notify_at": notify_at.isoformat(),
            "items": [
                {
                    "title": p.get("title", ""),
                    "current_bid": p.get("current_bid", "$0.00"),
                    "est_resale": p.get("est_resale", "Unknown"),
                    "url": p.get("url", ""),
                    "auction_title": p.get("auction_title", ""),
                }
                for p in picks
            ],
        })

    if rows:
        supabase_client.table("scheduled_notifications").insert(rows).execute()

    return len(rows)
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd "C:\Projects\First Project"
python -m unittest tests/test_notifications.py -v
```

Expected:
```
test_contains_auction_title ... ok
test_contains_auction_url ... ok
test_contains_bid ... ok
test_contains_est_resale ... ok
test_contains_item_title ... ok
test_empty_items_raises_value_error ... ok
test_falls_back_auction_title_when_missing ... ok
test_groups_flips_and_tools_by_auction ... ok
test_inserts_one_row_for_future_auction ... ok
test_returns_zero_when_no_picks ... ok
test_skips_auction_where_notify_at_is_in_the_past ... ok
----------------------------------------------------------------------
Ran 11 tests in 0.XXXs
OK
```

- [ ] **Step 5: Run all tests together**

```bash
cd "C:\Projects\First Project"
python -m unittest discover -s tests -v
```

Expected: All tests pass (14 from test_scout_utils + 11 from test_notifications = 25 total).

- [ ] **Step 6: Commit**

```bash
git add services/notifications.py tests/test_notifications.py
git commit -m "feat: add notifications service with body builder and schedule writer"
```

---

## Task 6: `streamlit_app.py` — Login gate

**Files:**
- Create: `streamlit_app.py`

- [ ] **Step 1: Create `streamlit_app.py`**

```python
import streamlit as st
from services.supabase_client import get_client

st.set_page_config(page_title="Equip-Bid Scout", page_icon="🔍", layout="centered")
st.title("Equip-Bid Scout")

if st.session_state.get("access_token"):
    st.success(f"Logged in as {st.session_state.get('user_email', '')}")
    if st.button("Log out"):
        get_client().auth.sign_out()
        for key in ["access_token", "refresh_token", "user_id", "user_email"]:
            st.session_state.pop(key, None)
        st.rerun()
    st.page_link("pages/1_Dashboard.py", label="Go to Dashboard →")
else:
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Log In"):
            try:
                client = get_client()
                resp = client.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.access_token = resp.session.access_token
                st.session_state.refresh_token = resp.session.refresh_token
                st.session_state.user_id = resp.user.id
                st.session_state.user_email = resp.user.email
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

        st.divider()
        reset_email = st.text_input("Email for password reset", key="reset_email")
        if st.button("Send Password Reset Email"):
            try:
                get_client().auth.reset_password_email(reset_email)
                st.success("Reset email sent. Check your inbox.")
            except Exception as e:
                st.error(f"Failed: {e}")

    with tab_signup:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password (min 6 characters)", type="password", key="signup_password")
        if st.button("Create Account"):
            try:
                get_client().auth.sign_up({"email": new_email, "password": new_password})
                st.success("Account created. Log in with your credentials above.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")
```

- [ ] **Step 2: Install dependencies locally**

```bash
pip install streamlit supabase requests beautifulsoup4
```

- [ ] **Step 3: Smoke test — run the app locally**

```bash
cd "C:\Projects\First Project"
streamlit run streamlit_app.py
```

Expected: Browser opens, shows Login and Sign Up tabs. Try logging in with a test account (create one in Supabase → Authentication → Users first). Confirm you see "Logged in as …" after successful login.

- [ ] **Step 4: Commit**

```bash
git add streamlit_app.py requirements.txt
git commit -m "feat: add Streamlit login gate with Supabase auth"
```

---

## Task 7: `pages/2_Settings.py`

**Files:**
- Create: `pages/2_Settings.py`

- [ ] **Step 1: Create `pages/` directory and `pages/2_Settings.py`**

```python
import streamlit as st
from services.supabase_client import get_client, require_auth

st.set_page_config(page_title="Settings — Equip-Bid Scout")
st.title("Settings")

user_id = require_auth()
client = get_client()

result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
settings = result.data[0] if result.data else {}

city = st.text_input(
    "City filter",
    value=settings.get("city", "wichita"),
    help="Case-insensitive substring matched against auction location (e.g. 'wichita')",
)

interest_text = st.text_area(
    "Interest keywords — one per line",
    value="\n".join(settings.get("interest_keywords") or []),
    height=250,
    help="Items whose title contains none of these are skipped",
)

tool_text = st.text_area(
    "Tool keywords — one per line",
    value="\n".join(settings.get("tool_keywords") or []),
    height=150,
    help="Items matching any of these go in the Tools section instead of Flips",
)

ntfy_topic = st.text_input(
    "ntfy.sh topic",
    value=settings.get("ntfy_topic") or "",
    help="Open the ntfy app → Subscribe → enter this value. Pick something unique.",
)

notify_minutes = st.slider(
    "Notify X minutes before auction closes",
    min_value=10,
    max_value=60,
    value=settings.get("notify_minutes") or 30,
)

if st.button("Save Settings", type="primary"):
    interest_keywords = [kw.strip() for kw in interest_text.splitlines() if kw.strip()]
    tool_keywords = [kw.strip() for kw in tool_text.splitlines() if kw.strip()]
    client.table("user_settings").upsert({
        "user_id": user_id,
        "city": city.strip().lower(),
        "interest_keywords": interest_keywords,
        "tool_keywords": tool_keywords,
        "ntfy_topic": ntfy_topic.strip(),
        "notify_minutes": notify_minutes,
    }).execute()
    st.success("Settings saved.")
```

- [ ] **Step 2: Smoke test — Settings page**

With the app running (`streamlit run streamlit_app.py`):
1. Log in
2. Navigate to Settings (sidebar)
3. Enter city = `wichita`, add a few keywords (e.g. `drill`, `dewalt`), enter your ntfy topic
4. Click Save
5. Refresh the page — confirm settings are pre-populated from Supabase

- [ ] **Step 3: Commit**

```bash
git add pages/2_Settings.py
git commit -m "feat: add Settings page with Supabase upsert"
```

---

## Task 8: `pages/3_Run_Tool.py`

**Files:**
- Create: `pages/3_Run_Tool.py`

- [ ] **Step 1: Create `pages/3_Run_Tool.py`**

```python
import streamlit as st
from services.supabase_client import get_client, require_auth
from services.scout import run_scout
from services.notifications import schedule_notifications

st.set_page_config(page_title="Run Tool — Equip-Bid Scout")
st.title("Run Scout")

user_id = require_auth()
client = get_client()

result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
if not result.data:
    st.warning("No settings found. Configure your settings before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

settings = result.data[0]

if not settings.get("ntfy_topic"):
    st.warning("ntfy.sh topic not set. Add it in Settings before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

if not settings.get("interest_keywords"):
    st.warning("No interest keywords configured. Add them in Settings before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

st.caption(f"City: **{settings['city']}** | ntfy topic: **{settings['ntfy_topic']}** | Notify **{settings.get('notify_minutes', 30)} min** before close")

if st.button("Run Scout", type="primary"):
    with st.spinner("Scanning equip-bid.com — this takes 30–60 seconds..."):
        try:
            results = run_scout(
                city_filter=[settings["city"]],
                interest_keywords=settings["interest_keywords"],
                tool_keywords=settings.get("tool_keywords") or [],
            )
        except Exception as e:
            st.error(f"Scout failed: {e}")
            st.stop()

    flips = results.get("flips", [])
    tools = results.get("tools", [])

    with st.expander(f"Flips — {len(flips)} found", expanded=True):
        if not flips:
            st.write("No flip candidates found this run.")
        for p in flips:
            st.markdown(f"**{p['title'][:80]}**")
            st.markdown(
                f"Bid: `{p['current_bid']}` &nbsp;|&nbsp; Est: `{p['est_resale']}` &nbsp;|&nbsp; Closes: {p['closing']}"
            )
            st.markdown(f"[View item →]({p['url']})")
            st.divider()

    with st.expander(f"Tools — {len(tools)} found", expanded=True):
        if not tools:
            st.write("No tool picks found this run.")
        for p in tools:
            st.markdown(f"**{p['title'][:80]}**")
            st.markdown(
                f"Bid: `{p['current_bid']}` &nbsp;|&nbsp; Est: `{p['est_resale']}` &nbsp;|&nbsp; Closes: {p['closing']}"
            )
            st.markdown(f"[View item →]({p['url']})")
            st.divider()

    client.table("watchlist_runs").insert({
        "user_id": user_id,
        "flips": flips,
        "tools": tools,
    }).execute()

    count = schedule_notifications(
        client,
        user_id,
        settings["ntfy_topic"],
        settings.get("notify_minutes") or 30,
        flips,
        tools,
    )

    st.success(f"Run complete. {count} auction notification(s) scheduled.")
```

- [ ] **Step 2: Smoke test — Run Tool page**

With the app running and settings saved:
1. Navigate to Run Tool
2. Click Run Scout
3. Wait ~30–60 seconds for results
4. Confirm flips and tools sections render
5. Confirm success message shows notification count
6. In Supabase → Table Editor → `watchlist_runs`: confirm a new row appeared
7. In Supabase → Table Editor → `scheduled_notifications`: confirm rows with future `notify_at` values

- [ ] **Step 3: Commit**

```bash
git add pages/3_Run_Tool.py
git commit -m "feat: add Run Tool page — scout, display, and schedule notifications"
```

---

## Task 9: `pages/1_Dashboard.py`

**Files:**
- Create: `pages/1_Dashboard.py`

- [ ] **Step 1: Create `pages/1_Dashboard.py`**

```python
import streamlit as st
from services.supabase_client import get_client, require_auth

st.set_page_config(page_title="Dashboard — Equip-Bid Scout")
st.title("Dashboard")

user_id = require_auth()
client = get_client()

st.markdown(f"Logged in as **{st.session_state.get('user_email', '')}**")
st.divider()

st.subheader("Last Run")
runs = (
    client.table("watchlist_runs")
    .select("generated_at, flips, tools")
    .eq("user_id", user_id)
    .order("generated_at", desc=True)
    .limit(1)
    .execute()
)

if runs.data:
    run = runs.data[0]
    flips = run.get("flips") or []
    tools = run.get("tools") or []
    ts = run["generated_at"][:16].replace("T", " ")
    st.markdown(f"**{ts} UTC** — {len(flips)} flip(s), {len(tools)} tool(s) found")
else:
    st.write("No runs yet.")

st.divider()

st.subheader("Upcoming Notifications")
pending = (
    client.table("scheduled_notifications")
    .select("auction_title, notify_at, auction_id")
    .eq("user_id", user_id)
    .eq("notified", False)
    .order("notify_at")
    .execute()
)

if pending.data:
    for row in pending.data:
        notify_time = row["notify_at"][:16].replace("T", " ")
        title = (row.get("auction_title") or row["auction_id"])[:60]
        st.markdown(f"- **{title}** — notify at {notify_time} UTC")
else:
    st.write("No pending notifications. Run the scout to schedule some.")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/3_Run_Tool.py", label="Run Scout →")
with col2:
    st.page_link("pages/2_Settings.py", label="Settings →")
```

- [ ] **Step 2: Smoke test — Dashboard page**

With the app running (after at least one Run Tool execution):
1. Navigate to Dashboard
2. Confirm last run timestamp, flip count, tool count appear
3. Confirm upcoming notification rows list correctly
4. Confirm navigation links work

- [ ] **Step 3: Commit**

```bash
git add pages/1_Dashboard.py
git commit -m "feat: add Dashboard page with last run summary and upcoming notifications"
```

---

## Task 10: `scripts/dispatcher.py`

**Files:**
- Create: `scripts/dispatcher.py`
- Create: `tests/test_dispatcher.py`

- [ ] **Step 1: Create `tests/test_dispatcher.py` with failing tests**

```python
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
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd "C:\Projects\First Project"
python -m unittest tests/test_dispatcher.py -v 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'scripts.dispatcher'`

- [ ] **Step 3: Create `scripts/dispatcher.py`**

```python
#!/usr/bin/env python3
"""
scripts/dispatcher.py
Run by GitHub Actions every 15 minutes.
Reads scheduled_notifications from Supabase and fires ntfy.sh pushes for due rows.
Uses SUPABASE_SERVICE_KEY (bypasses RLS) to read across all users.
"""

import os
import sys
from datetime import datetime, timezone

import requests
from supabase import create_client

BASE_URL = "https://www.equip-bid.com"


def build_ntfy_body(auction_id: str, items: list[dict]) -> str:
    auction_title = items[0].get("auction_title", f"Auction {auction_id}") if items else f"Auction {auction_id}"
    lines = [f"Auction: {auction_title}"]
    for item in items:
        title = item.get("title", "")[:60]
        bid = item.get("current_bid", "?")
        resale = item.get("est_resale", "?")
        lines.append(f"• {title}  |  Bid: {bid}  |  Est: {resale}")
    lines.append(f"{BASE_URL}/auction/{auction_id}")
    return "\n".join(lines)


def post_ntfy(topic: str, body: str) -> None:
    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": "⏰ Equip-Bid — closing soon",
            "Priority": "high",
            "Tags": "bell",
        },
        timeout=10,
    )
    resp.raise_for_status()


def main() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    supabase = create_client(url, key)

    now = datetime.now(timezone.utc).isoformat()
    result = (
        supabase.table("scheduled_notifications")
        .select("*")
        .lte("notify_at", now)
        .eq("notified", False)
        .execute()
    )

    rows = result.data
    if not rows:
        print("No notifications due.")
        return

    notified_ids = []
    for row in rows:
        auction_id = row["auction_id"]
        topic = row["ntfy_topic"]
        items = row["items"]
        try:
            body = build_ntfy_body(auction_id, items)
            post_ntfy(topic, body)
            notified_ids.append(row["id"])
            print(f"[OK] auction {auction_id} → {topic} ({len(items)} item(s))")
        except Exception as e:
            print(f"[ERROR] auction {auction_id}: {e}")

    if notified_ids:
        sent_at = datetime.now(timezone.utc).isoformat()
        supabase.table("scheduled_notifications")\
            .update({"notified": True, "notified_at": sent_at})\
            .in_("id", notified_ids)\
            .execute()

    print(f"\n{len(notified_ids)}/{len(rows)} notification(s) sent.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd "C:\Projects\First Project"
python -m unittest tests/test_dispatcher.py -v
```

Expected:
```
test_contains_auction_title ... ok
test_contains_auction_url ... ok
test_contains_bid ... ok
test_contains_item_title ... ok
test_posts_to_correct_url ... ok
test_raises_on_http_error ... ok
----------------------------------------------------------------------
Ran 6 tests in 0.XXXs
OK
```

- [ ] **Step 5: Run all tests together**

```bash
cd "C:\Projects\First Project"
python -m unittest discover -s tests -v
```

Expected: All 31 tests pass (14 + 11 + 6).

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/dispatcher.py tests/test_dispatcher.py
git commit -m "feat: add dispatcher script and tests"
```

---

## Task 11: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/notify_dispatcher.yml`
- Delete or disable: old equip-bid workflow (whichever yml currently runs `equip_bid_check.py`)

- [ ] **Step 1: Find and delete the old workflow**

```bash
ls .github/workflows/
```

Delete any workflow file that references `equip_bid_check.py`:

```bash
rm .github/workflows/<old-workflow-name>.yml
```

- [ ] **Step 2: Create `.github/workflows/notify_dispatcher.yml`**

```yaml
name: Notification Dispatcher

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  dispatch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install supabase requests
      - name: Run dispatcher
        run: python scripts/dispatcher.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
```

- [ ] **Step 3: Add secrets to GitHub repository**

Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret name | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL (e.g. `https://abcdefgh.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | Your Supabase service role key (from Project Settings → API) |

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/notify_dispatcher.yml
git commit -m "feat: add GitHub Actions notification dispatcher workflow"
git push
```

- [ ] **Step 5: Test with manual trigger**

In GitHub → Actions → Notification Dispatcher → Run workflow.

Expected run log (if scheduled_notifications has due rows):
```
[OK] auction 45612 → your-ntfy-topic (2 item(s))

1/1 notification(s) sent.
```

Or if no rows are due:
```
No notifications due.
```

Confirm the workflow completes with green status.

---

## Task 12: Streamlit Cloud deployment

- [ ] **Step 1: Ensure the repo is on GitHub and up to date**

```bash
git push
```

- [ ] **Step 2: Connect to Streamlit Cloud**

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click **New app**
4. Select your repository, branch `master`, main file `streamlit_app.py`
5. Click **Deploy**

- [ ] **Step 3: Add secrets in Streamlit Cloud**

In your deployed app → Settings → Secrets, paste:

```toml
SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_KEY = "your-anon-public-key"
```

Click **Save** — the app will restart automatically.

- [ ] **Step 4: End-to-end smoke test**

1. Open the deployed Streamlit URL in your browser
2. Sign up for a new account (or log in)
3. Go to Settings → fill in city, keywords, ntfy topic → Save
4. Go to Run Tool → click Run Scout → confirm results load
5. Check Supabase → `scheduled_notifications` for new rows
6. In the ntfy app, confirm your topic is subscribed
7. Trigger the dispatcher manually (GitHub → Actions → Run workflow) and confirm push arrives on your phone

- [ ] **Step 5: Verify cron fires automatically**

Wait up to 15 minutes after a scheduled notification's `notify_at` time. Confirm:
- Push notification arrives on phone
- GitHub Actions run log shows `[OK] auction …`
- Supabase row shows `notified = true`
