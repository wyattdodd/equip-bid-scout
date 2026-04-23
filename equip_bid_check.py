#!/usr/bin/env python3
"""
equip_bid_check.py
Runs in GitHub Actions every 30 minutes.
Reads watchlist.json and sends an ntfy.sh push for any auction
closing within the next 20-55 minutes.

Usage:
    python equip_bid_check.py

Requires:
    pip install requests
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
NTFY_TOPIC     = "equip-bid-wichita"
WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"
BASE_URL       = "https://www.equip-bid.com"

# Notify when auction closes in this window (minutes).
# Wide enough that the 30-min cron always catches each auction once.
ALERT_MIN = 20
ALERT_MAX = 55
# ──────────────────────────────────────────────────────────────────────────────


def parse_closing_utc(utc_str: str | None) -> datetime | None:
    """Parse 'YYYY-MM-DD HH:MM:SS UTC' into a UTC-aware datetime."""
    if not utc_str:
        return None
    try:
        clean = utc_str.replace(" UTC", "").strip()
        dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_body(auction_id: str, picks: list[dict]) -> str:
    auction_title = picks[0].get("auction_title", f"Auction {auction_id}")
    lines = [f"Auction: {auction_title}"]
    for p in picks:
        title = p.get("title", "(no title)")[:60]
        bid   = p.get("current_bid", "?")
        resale = p.get("est_resale", "?")
        lines.append(f"• {title}  |  Bid: {bid}  |  Est: {resale}")
    lines.append(f"{BASE_URL}/auction/{auction_id}")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true",
                        help="Send a test notification immediately, ignoring time window")
    args = parser.parse_args()

    if args.test:
        body = "This is a test notification from equip-bid-scout.\nIf you see this, ntfy.sh is working."
        try:
            resp = requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=body.encode("utf-8"),
                headers={
                    "Title": "Equip-Bid test notification",
                    "Priority": "default",
                    "Tags": "white_check_mark",
                },
                timeout=10,
            )
            resp.raise_for_status()
            print(f"[OK] Test notification sent to ntfy.sh topic '{NTFY_TOPIC}'")
        except Exception as e:
            print(f"[ERROR] ntfy.sh POST failed: {e}")
            sys.exit(1)
        sys.exit(0)

    if not WATCHLIST_PATH.exists():
        print("No watchlist.json — nothing to check.")
        sys.exit(0)

    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ERROR] watchlist.json is not valid JSON: {e}")
            sys.exit(1)

    picks = data.get("flips", []) + data.get("tools", [])
    if not picks:
        picks = data.get("picks", [])  # backwards compat with old watchlist format
    if not picks:
        print("Watchlist is empty.")
        sys.exit(0)

    now = datetime.now(timezone.utc)

    # Group by auction_id
    auctions: dict[str, list[dict]] = {}
    for pick in picks:
        aid = pick.get("auction_id", "")
        if aid:
            auctions.setdefault(aid, []).append(pick)

    notified = 0
    for auction_id, auction_picks in auctions.items():
        closing_dt = parse_closing_utc(auction_picks[0].get("closing_utc"))
        if not closing_dt:
            continue

        minutes_left = (closing_dt - now).total_seconds() / 60
        if not (ALERT_MIN <= minutes_left <= ALERT_MAX):
            continue

        body = build_body(auction_id, auction_picks)
        try:
            resp = requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=body.encode("utf-8"),
                headers={
                    "Title": "⏰ Equip-Bid — 30 min left",
                    "Priority": "high",
                    "Tags": "bell",
                },
                timeout=10,
            )
            resp.raise_for_status()
            print(f"[OK] Notified auction {auction_id} ({minutes_left:.0f} min left)")
            notified += 1
        except Exception as e:
            print(f"[ERROR] ntfy.sh failed for auction {auction_id}: {e}")
            sys.exit(1)

    if notified == 0:
        print(f"No auctions in {ALERT_MIN}-{ALERT_MAX} min window. Nothing sent.")


if __name__ == "__main__":
    main()
