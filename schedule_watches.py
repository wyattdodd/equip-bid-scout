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
    """Parse closing time string into a timezone-aware datetime. Returns None on failure.

    Handles two formats written by equip_bid_scout.py:
      'YYYY-MM-DD HH:MM:SS UTC'   — explicit UTC
      'YYYY-MM-DD HH:MM:SS LOCAL' — local system time (auction display time)
    """
    if not utc_str:
        return None
    try:
        if utc_str.endswith(" UTC"):
            clean = utc_str[:-4].strip()
            dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        if utc_str.endswith(" LOCAL"):
            clean = utc_str[:-6].strip()
            dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
            local_tz = datetime.now().astimezone().tzinfo
            return dt.replace(tzinfo=local_tz)
        return None
    except Exception:
        return None


def register_job(auction_id: str, trigger_local: datetime) -> bool:
    """Register a one-time Task Scheduler job. Returns True on success."""
    job_name  = f"EquipBid-{auction_id}"
    date_str  = trigger_local.strftime("%m/%d/%Y")
    time_str  = trigger_local.strftime("%H:%M")
    # auction_id quoted to handle any future non-numeric IDs
    command   = f'"{PYTHON_EXE}" "{NOTIFY_SCRIPT}" --auction "{auction_id}"'

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
    if result.returncode != 0:
        # schtasks writes errors to stdout on Windows
        detail = (result.stdout or result.stderr or "no output").strip()
        print(f"  [ERROR] schtasks failed for auction {auction_id}: {detail}")
        return False
    return True


def main():
    if not WATCHLIST_PATH.exists():
        print(f"[ERROR] watchlist.json not found at {WATCHLIST_PATH}")
        print("Run equip_bid_scout.py first.")
        sys.exit(1)

    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ERROR] watchlist.json is not valid JSON: {e}")
            sys.exit(1)

    picks = data.get("picks", [])
    if not picks:
        print("No picks in watchlist. Run equip_bid_scout.py first.")
        sys.exit(0)

    now = datetime.now(timezone.utc)
    scheduled = 0
    skipped = 0

    # Deduplicate: one job per auction, preferring picks with a non-null closing_utc
    best: dict[str, dict] = {}
    for pick in picks:
        aid = pick.get("auction_id", "")
        if not aid:
            print(f"  [SKIP] Pick missing auction_id — '{pick.get('title', '')[:50]}'")
            skipped += 1
            continue
        if aid not in best or best[aid].get("closing_utc") is None:
            best[aid] = pick

    for auction_id, pick in best.items():
        closing_dt = parse_closing_utc(pick.get("closing_utc"))
        if not closing_dt:
            print(f"  [SKIP] No valid closing time for auction {auction_id} — '{pick.get('title', '')[:50]}'")
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
            skipped += 1

    print(f"\n{scheduled} job(s) scheduled, {skipped} skipped.")
    if scheduled > 0:
        print("View or delete jobs: open Task Scheduler → Task Scheduler Library → search 'EquipBid'")


if __name__ == "__main__":
    main()
