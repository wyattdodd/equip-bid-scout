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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.notifications import build_ntfy_body


def post_ntfy(topic: str, body: str) -> None:
    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": "Equip-Bid - closing soon",
            "Priority": "high",
            "Tags": "bell",
        },
        timeout=10,
    )
    resp.raise_for_status()


def main() -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url:
        sys.exit("SUPABASE_URL environment variable is not set")
    if not key:
        sys.exit("SUPABASE_SERVICE_KEY environment variable is not set")
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
        try:
            auction_id = row["auction_id"]
            topic = row["ntfy_topic"]
            items = row["items"]
            body = build_ntfy_body(auction_id, items)
            post_ntfy(topic, body)
            notified_ids.append(row["id"])
            print(f"[OK] auction {auction_id} → {topic} ({len(items)} item(s))")
        except Exception as e:
            print(f"[ERROR] row {row.get('id', '?')}: {e}")

    if notified_ids:
        sent_at = datetime.now(timezone.utc).isoformat()
        supabase.table("scheduled_notifications") \
            .update({"notified": True, "notified_at": sent_at}) \
            .in_("id", notified_ids) \
            .execute()

    print(f"\n{len(notified_ids)}/{len(rows)} notification(s) sent.")


if __name__ == "__main__":
    main()
