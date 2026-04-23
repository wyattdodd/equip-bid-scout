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
        title = p.get("title", "(no title)")[:60]
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


def filter_picks(data: dict, auction_id: str) -> list[dict]:
    """Return picks from watchlist data matching the given auction ID."""
    return [p for p in data.get("picks", []) if p.get("auction_id") == auction_id]


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
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ERROR] watchlist.json is not valid JSON: {e}")
            sys.exit(1)

    picks = filter_picks(data, auction_id)

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
