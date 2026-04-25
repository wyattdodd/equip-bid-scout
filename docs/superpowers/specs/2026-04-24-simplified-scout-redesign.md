# Simplified Scout Redesign

**Date:** 2026-04-24
**Status:** Approved

## Goal

Replace the arbitrage-scoring / Flips+Tools split with a simpler model: show the 10 items with the highest estimated retail value that match the user's interest keywords and don't match any reject phrase.

---

## Changes

### 1. Supabase — `user_settings` table

Add one column:

```sql
ALTER TABLE user_settings ADD COLUMN reject_phrases text[] DEFAULT '{}';
```

### 2. `services/scout.py`

- Remove `tool_keywords` parameter from `run_scout()`.
- Remove `score_item()` (arbitrage scoring logic).
- Remove hardcoded `EXCLUSION_PHRASES` constant.
- New ranking logic in `run_scout()`:
  1. Collect all items matching interest keywords.
  2. Drop any item whose lowercased title contains any reject phrase (case-insensitive substring match, same as current exclusion logic).
  3. For each surviving item, compute `_ref` via `extract_retail()` (stated retail in title) or `lookup_brand()` (brand value table midpoint). Items with `_ref < MIN_RESALE_VALUE` (75) or `_ref == 0` are dropped.
  4. Sort survivors by `_ref` descending.
  5. Return top 10 as a flat list via `_clean_pick()`.
- `run_scout()` signature becomes:
  ```python
  def run_scout(city_filter, interest_keywords, reject_phrases) -> dict:
      # returns {"picks": [...], "errors": int}
  ```
- Remove `_is_tool()` — no longer needed.
- `TOP_PICKS = 10` replaces `TOP_FLIPS = 5` / `TOP_TOOLS = 5`.

### 3. `pages/2_Settings.py`

- Remove the "Tool keywords" text area and its save logic.
- Add a "Reject phrases — one per line" text area.
- On first load (when `reject_phrases` is empty/absent), pre-populate the text area with the default phrase list (moved from the old `EXCLUSION_PHRASES` constant into a `DEFAULT_REJECT_PHRASES` list in the settings page).
- Save `reject_phrases` to Supabase on Save.

### 4. `pages/3_Run_Tool.py`

- Pass `reject_phrases` (from settings) to `run_scout()` instead of `tool_keywords`.
- Replace the two expanders (Flips / Tools) with one flat list labeled "Top Picks — {n} found".
- Pass `picks` (flat list) to `schedule_notifications()`.

### 5. `services/notifications.py`

- `schedule_notifications()` currently takes `flips` and `tools` as separate params. Change to a single `picks` list:
  ```python
  def schedule_notifications(client, user_id, ntfy_topic, notify_minutes, picks) -> int:
  ```
- Internal grouping by auction_id is unchanged.

### 6. `pages/3_Run_Tool.py` — `watchlist_runs` write

The `watchlist_runs` table has `flips jsonb` and `tools jsonb` columns. No schema migration needed: store `picks` in the `flips` column and an empty list in `tools`.

```python
client.table("watchlist_runs").insert({
    "user_id": user_id,
    "flips": picks,
    "tools": [],
}).execute()
```

### 7. `scripts/dispatcher.py`

- No logic changes needed — dispatcher reads `scheduled_notifications` rows directly from Supabase, independent of the flips/tools split.

### 8. `tests/test_scout_utils.py`

- Remove `TestIsTool` (function deleted).
- Update any test that calls `run_scout()` with the old signature.
- Add tests for the new ranking logic (rank by `_ref`, reject phrases filter).

### 9. `tests/test_notifications.py`

- Update `TestScheduleNotifications` to call the new single-`picks` signature.

---

## Default Reject Phrases

Moved verbatim from the old `EXCLUSION_PHRASES` constant in `scout.py`:

```
case for, case compatible, compatible with, replacement for, adapter for,
charger for, screen protector, tempered glass, silicone case, phone case,
tablet case, carrying case, travel case, hard case, protective case,
cover for, stand for, holder for, mount for, laptop case, laptop bag,
laptop backpack, laptop sleeve, laptop stand, laptop riser, laptop desk,
couch cover, sofa cover, chair cover, sectional cover, slipcover,
slip cover, furniture cover, cushion cover, cushion replacement,
upholstery foam, backup camera, rear camera, reverse camera, dash cam,
baby camera, baby monitor, car camera, parking camera, camera strap,
camera bag, lens cap, headphone stand, speaker stand, earbud tips,
actuator, rmt motor, lift motor, replacement legs, furniture legs,
sofa legs, couch legs, rv seat, seat cover, outdoor cushion, chair cushion,
patio cushion, cushion set, missing, parts only, for parts, not working,
as is, damaged, cracked screen
```

---

## What Does Not Change

- Auth flow (`streamlit_app.py`, `services/supabase_client.py`)
- Dashboard page
- Scraping logic (`get_nearby_auctions`, `get_auction_items`, `_parse_closing_span`)
- Brand value table (`BRAND_VALUE`) and `lookup_brand()` / `extract_retail()` helpers
- Dispatcher script and GitHub Actions workflow
- Notification body building (`build_ntfy_body`)
