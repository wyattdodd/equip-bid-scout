# Streamlit + Supabase Rebuild — Design Spec
**Date:** 2026-04-23
**Status:** Approved

## Goal

Rebuild the local CLI-based equip-bid arbitrage scout into a multi-user Streamlit web application. Users log in, configure their own city, keywords, and ntfy.sh topic, run the scout from the browser, and receive phone push notifications before watched auctions close — all without their PC being on.

Everything runs free in the cloud: Streamlit Cloud (UI), Supabase (auth + database), GitHub Actions (notification dispatcher), ntfy.sh (phone push).

---

## Architecture

```
┌─────────────────────────────────┐
│  Streamlit Cloud (UI)           │
│  Login → Dashboard → Settings   │
│  → Run Tool                     │
└────────────┬────────────────────┘
             │ supabase-py (anon key, RLS enforced)
             ▼
┌─────────────────────────────────┐
│  Supabase                       │
│  Auth (email/password)          │
│  Postgres:                      │
│    user_settings                │
│    watchlist_runs               │
│    scheduled_notifications      │
└────────────┬────────────────────┘
             │ service key (bypasses RLS)
             ▼
┌─────────────────────────────────┐
│  GitHub Actions (every 15 min)  │
│  scripts/dispatcher.py          │
│  → reads scheduled_notifications│
│    WHERE notify_at <= now()     │
│    AND notified = false         │
│  → POST ntfy.sh per user/auction│
│  → marks notified = true        │
└────────────┬────────────────────┘
             │ HTTP POST
             ▼
         ntfy.sh → Phone
```

### Run Tool flow

1. User clicks Run → scout scrapes equip-bid.com using their city + keywords from Supabase
2. Results displayed in browser (flips + tools sections)
3. App calculates `notify_at = closing_utc - notify_minutes` for each unique auction in top picks
4. Old unnotified `scheduled_notifications` rows for this user deleted; fresh rows inserted
5. Full results written to `watchlist_runs` for Dashboard display

### Dispatcher flow

1. GitHub Actions cron fires every 15 minutes (~720 min/month, within free tier)
2. Connects with service key, queries `scheduled_notifications WHERE notify_at <= now() AND notified = false`
3. Groups rows by `(user_id, auction_id)` — one ntfy.sh POST per auction per user
4. Marks rows `notified = true`, sets `notified_at = now()`
5. Run log in GitHub Actions shows what was sent

---

## Database Schema

RLS enabled on all tables. Users read/write only their own rows. Dispatcher uses service key to read across all users.

### `user_settings`
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
```

### `watchlist_runs`
```sql
CREATE TABLE watchlist_runs (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        REFERENCES auth.users(id),
  generated_at timestamptz DEFAULT now(),
  flips        jsonb       DEFAULT '[]',
  tools        jsonb       DEFAULT '[]'
);
```

### `scheduled_notifications`
```sql
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

`items` is an array of `{title, current_bid, est_resale, url}` objects — one per pick from that auction.

`ntfy_topic` is copied from `user_settings` at run time so topic changes don't affect already-scheduled notifications.

### RLS Policies (applied identically to all three tables)
```sql
-- Repeat for user_settings, watchlist_runs, scheduled_notifications
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

---

## Project Structure

```
First Project/
├── streamlit_app.py              # Entry point — login/signup gate
├── pages/
│   ├── 1_Dashboard.py            # Last run summary, upcoming notifications
│   ├── 2_Settings.py             # City, keywords, ntfy topic, save to Supabase
│   └── 3_Run_Tool.py             # Run scout, display results, schedule notifications
├── services/
│   ├── supabase_client.py        # Shared client init from st.secrets
│   ├── scout.py                  # Refactored equip_bid_scout.py — no hardcoded config
│   └── notifications.py          # Schedule writes + ntfy body builder
├── scripts/
│   └── dispatcher.py             # GitHub Actions runner — reads Supabase, fires ntfy.sh
├── .github/
│   └── workflows/
│       └── notify_dispatcher.yml
├── .streamlit/
│   └── secrets.toml              # Template only — gitignored
├── tests/
│   ├── test_scout_utils.py       # Existing tests updated for new signatures
│   └── test_dispatcher.py        # New tests for dispatcher logic
├── requirements.txt
└── docs/superpowers/specs/       # This file
```

### File migration

| Current file | Destination | Change |
|---|---|---|
| `equip_bid_scout.py` | `services/scout.py` | Hardcoded config removed; accepts user settings as params |
| `equip_bid_check.py` | `scripts/dispatcher.py` | Reads Supabase instead of `watchlist.json` |
| `main.py` | Deleted | Replaced by `pages/3_Run_Tool.py` |
| `watchlist.json` | Removed from git | Replaced by `watchlist_runs` table |
| existing GHA workflow | `.github/workflows/notify_dispatcher.yml` | Dispatcher replaces equip_bid_check workflow |

---

## Streamlit Pages

### `streamlit_app.py` — Login Gate

Two tabs: Login and Sign Up. Password reset link below login form. On success, stores Supabase session in `st.session_state`. All pages check for valid session at top and redirect here if missing.

### `pages/1_Dashboard.py`

- Greeting with user email
- Last Run card: timestamp, flip count, tool count (from most recent `watchlist_runs` row)
- Upcoming Notifications card: `scheduled_notifications` rows where `notified = false`, showing auction title and notify time
- Navigation buttons to Settings and Run Tool

### `pages/2_Settings.py`

- **City** — text input fed into `NEARBY_FILTER` (case-insensitive substring match against auction location)
- **Interest keywords** — `st.text_area`, one keyword per line, pre-populated from Supabase on load. Saved as `text[]` by splitting on newlines and stripping blank lines.
- **Tool keywords** — same, separate text area, same split-on-newline storage
- **ntfy.sh topic** — single text input with setup instructions
- **Notify X minutes before close** — `st.slider`, 10–60 min, default 30
- **Save** button — upserts `user_settings`, shows success message
- Warning banner if settings are empty, linking here from Run Tool page

### `pages/3_Run_Tool.py`

- Guard: if no `user_settings` row or `ntfy_topic` is blank, show warning and stop
- "Run Scout" button
- On click: `st.spinner` while scout runs (30–60 sec typical)
- Results in two `st.expander` sections (Flips, Tools) matching current output format
- After results: writes `watchlist_runs` row, replaces `scheduled_notifications` rows
- Summary: "X notifications scheduled for Y auctions"

---

## Services

### `services/supabase_client.py`

Initialises the Supabase client from `st.secrets`. Single function `get_client()` used by all pages.

### `services/scout.py`

Refactored from `equip_bid_scout.py`. Hardcoded `NEARBY_FILTER`, `INTEREST_KEYWORDS`, `TOOL_KEYWORDS` removed from module scope. Core entry point:

```python
def run_scout(city_filter: list[str],
              interest_keywords: list[str],
              tool_keywords: list[str]) -> dict:
    # returns {"flips": [...], "tools": [...]}
```

All scoring logic (`score_item`, `BRAND_VALUE`, `extract_retail`, `lookup_brand`, etc.) unchanged. `_print_section` removed — caller renders results via Streamlit components.

### `services/notifications.py`

```python
def schedule_notifications(supabase, user_id, settings, picks_by_auction) -> int:
    # Deletes old unnotified rows for user, inserts fresh rows
    # Returns count of rows inserted

def build_ntfy_body(auction_id, items) -> str:
    # Same logic as existing build_body() in equip_bid_check.py
```

---

## GitHub Actions Dispatcher

### `.github/workflows/notify_dispatcher.yml`

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
      - run: pip install supabase requests
      - run: python scripts/dispatcher.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
```

### `scripts/dispatcher.py`

1. Connect with service key
2. Query `scheduled_notifications WHERE notify_at <= now() AND notified = false`
3. Group by `(user_id, auction_id)`
4. POST to `ntfy.sh/{ntfy_topic}` for each group
5. Update rows: `notified = true`, `notified_at = now()`
6. Print summary (visible in Actions run log)
7. If ntfy.sh POST fails for one user/auction: log the error and continue — do not abort the run or re-mark rows as notified

### Keys

| Key | Used by | Scope |
|---|---|---|
| `SUPABASE_KEY` (anon) | Streamlit app via `st.secrets` | RLS enforced — own rows only |
| `SUPABASE_SERVICE_KEY` | Dispatcher via GHA secret | RLS bypassed — all rows |

Service key never touches the Streamlit app or the repo.

---

## Secrets Configuration

### `.streamlit/secrets.toml` (template — gitignored)
```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key"
```

### GitHub Actions secrets
```
SUPABASE_URL
SUPABASE_SERVICE_KEY
```

---

## What Does Not Change

- All scoring logic: `score_item`, `BRAND_VALUE`, `extract_retail`, `lookup_brand`, `parse_dollar`
- Closing time parsing: `_parse_closing_span`, `_UTC_RE`
- Scraping logic: `get_nearby_auctions`, `get_auction_items`
- Exclusion phrases and minimum resale threshold
- ntfy.sh notification format and body structure
- Existing unit tests (signatures updated to match new function params)

---

## Out of Scope

- Admin page (users managed directly in Supabase dashboard)
- Bid monitoring between scout runs
- Pagination for large auctions
- Output history beyond the last run per user
- Self-serve user onboarding (developer sets up each user's keywords)
