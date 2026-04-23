# Equip-Bid Auction Watcher — Design Spec
**Date:** 2026-04-22  
**Status:** Approved

## Goal

After running the scout and seeing the top picks, automatically receive a push notification on your phone 30 minutes before each watched auction closes — so you can return at the most active bidding window and decide whether to buy.

Everything runs locally on Windows. No paid services. No persistent processes.

---

## Components

| File | Role |
|---|---|
| `equip_bid_scout.py` | Modified — capture UTC closing datetime from HTML, save `watchlist.json` after displaying results |
| `schedule_watches.py` | New — reads `watchlist.json`, registers one Windows Task Scheduler job per auction timed 30 min before close |
| `equip_bid_notify.py` | New — called by Task Scheduler at trigger time, reads `watchlist.json`, sends ntfy.sh push notification |
| `watchlist.json` | Written by scout each run, read by the other two scripts |

Scripts are kept separate so any one of them can be skipped, re-run, or replaced independently.

---

## Data Flow

```
1. py equip_bid_scout.py
   → scrapes & scores as today
   → displays top 5 picks
   → saves watchlist.json
   → prints reminder to run schedule_watches.py

2. py schedule_watches.py
   → reads watchlist.json
   → calculates (closing_utc − 30 min) for each pick
   → registers Windows Task Scheduler job named "EquipBid-{auction_id}"
   → prints confirmation of what was scheduled
   → skips any auction closing in < 30 min (prints warning)

3. At trigger time, Windows calls:
   py equip_bid_notify.py --auction {auction_id}
   → reads watchlist.json
   → finds all picks from that auction (grouped)
   → HTTP POST to ntfy.sh → push notification to phone

4. Phone receives:
   "30 min left — Auction Title
    • DeWalt Drill Kit  |  Bid: $5  |  Est: $80-$200
    • Milwaukee Impact  |  Bid: $0  |  Est: $100-$300
    [auction link]"
```

---

## `watchlist.json` Format

Overwritten each time the scout runs.

```json
{
  "generated": "2026-04-22T14:30:00Z",
  "picks": [
    {
      "title": "DeWalt 20V MAX Drill Driver Kit",
      "current_bid": "$5.00",
      "est_resale": "$80-$200 (brand: dewalt)",
      "closing_utc": "2026-04-22T20:00:00Z",
      "closing_display": "5 hours 30 min",
      "url": "https://www.equip-bid.com/auction/12345/item/67890",
      "auction_id": "12345"
    }
  ]
}
```

---

## Configuration

**`equip_bid_scout.py`** (existing config block, one addition):
```python
WATCHLIST_PATH = "watchlist.json"
```

**`schedule_watches.py`** and **`equip_bid_notify.py`** (top of each file):
```python
NTFY_TOPIC     = "equip-bid-wichita"   # subscribe to this in the ntfy app
WATCHLIST_PATH = "watchlist.json"
```

Topic name acts as a lightweight password — pick something unique to you.

---

## Closing Time Fix (Scout Modification)

The current scout reads the countdown display text from the timer span. For scheduling we also need the absolute UTC time, which is already present in the `title` attribute of the same element:

```html
<span title="2026-04-22 20:00:00 UTC">5 hours 30 min</span>
```

The scout will capture both:
- `closing_display` — the `.get_text()` string (shown in terminal output, unchanged)
- `closing_utc` — parsed from `span["title"]`, stored in `watchlist.json`

---

## Task Scheduler Jobs

Each job is named `EquipBid-{auction_id}` — unique per auction, easy to find in Task Scheduler UI.

- Created with `schtasks /create ... /f` — `/f` overwrites if the job already exists, so re-running `schedule_watches.py` is safe.
- Trigger: one-time, at `closing_utc − 30 minutes`, converted to local time for `schtasks`.
- Action uses **absolute paths** (Task Scheduler does not inherit working directory): `schedule_watches.py` resolves its own `__file__` directory at runtime and embeds the full path to `python3.13.exe` and `equip_bid_notify.py` in the registered command.
- Jobs are not automatically deleted after firing. User can clear them via Task Scheduler or a future cleanup script.

---

## ntfy.sh Notification Format

One POST per auction (not per item). Multiple picks from the same auction are grouped.

```
Title:    "⏰ Equip-Bid — 30 min left"
Body:     "Auction: {auction title}
           • {item title}  |  Bid: {bid}  |  Est: {resale}
           • ...
           {auction url}"
Priority: high
```

---

## Edge Cases

| Situation | Behavior |
|---|---|
| Auction closes in < 30 min at schedule time | Skip, print warning — too late |
| Scout run twice same day | `watchlist.json` overwritten; re-run `schedule_watches.py` to refresh jobs |
| `closing_utc` missing/unparseable | Skip that pick, print warning with item title |
| ntfy.sh POST fails | Print error — visible in Task Scheduler run log; no retry |
| Multiple picks from same auction | Grouped into one notification |

---

## ntfy App Setup (One-Time)

1. Install **ntfy** from the App Store / Google Play
2. Tap **Subscribe to topic** → enter your `NTFY_TOPIC` value
3. Done — no account needed

---

## Out of Scope

- Automatic cleanup of fired Task Scheduler jobs
- Bid change monitoring between scout run and close (just a one-time alert)
- Pagination for large auctions (existing limitation, separate concern)
- Output logging / history of past picks
