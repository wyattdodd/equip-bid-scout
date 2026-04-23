#!/usr/bin/env python3
"""
main.py
Orchestrates the full Equip-Bid workflow:
  1. Scout  — scrape and score picks
  2. Review — optionally reject picks
  3. Push   — commit watchlist.json to GitHub (triggers cloud alerts via GitHub Actions)

Usage:
    py main.py
"""

import json
import subprocess
import sys
from pathlib import Path

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"
SCOUT_SCRIPT   = Path(__file__).parent / "equip_bid_scout.py"


def prompt_rejection(picks: list[dict]) -> list[dict]:
    """Show picks and let the user reject any before scheduling."""
    print("\n" + "=" * 68)
    print("   REVIEW — type numbers to skip, or Enter to keep all")
    print("=" * 68)

    for i, p in enumerate(picks, 1):
        print(f"\n#{i}  {p['title'][:78]}")
        print(f"    Bid: {p['current_bid']}  |  Est: {p.get('est_resale', 'Unknown')}")
        print(f"    Closes: {p['closing']}")
        print(f"    {p['url']}")

    print("\nSkip which picks? (e.g. '2 4', or Enter to keep all): ", end="", flush=True)

    try:
        response = input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return picks

    if not response:
        return picks

    try:
        skip_nums = {int(n) for n in response.split()}
    except ValueError:
        print("[WARN] Could not parse input — keeping all picks.")
        return picks

    kept = [p for i, p in enumerate(picks, 1) if i not in skip_nums]
    removed = len(picks) - len(kept)
    if removed:
        print(f"\n{removed} pick(s) removed. {len(kept)} kept for scheduling.")
    return kept


def main():
    # ── Step 1: Scout ─────────────────────────────────────────────────────────
    result = subprocess.run([sys.executable, str(SCOUT_SCRIPT)])
    if result.returncode != 0:
        print("[ERROR] Scout failed.")
        sys.exit(1)

    if not WATCHLIST_PATH.exists():
        print("[ERROR] watchlist.json was not written.")
        sys.exit(1)

    # ── Step 2: Review ────────────────────────────────────────────────────────
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)

    picks = data.get("picks", [])
    if not picks:
        print("\nNo picks to schedule.")
        sys.exit(0)

    picks = prompt_rejection(picks)

    if not picks:
        print("\nAll picks rejected. Nothing scheduled.")
        sys.exit(0)

    # Re-save with only the kept picks
    data["picks"] = picks
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # ── Step 3: Push watchlist to GitHub (triggers cloud alerts) ─────────────
    print("\nPushing watchlist to GitHub...")
    try:
        subprocess.run(["git", "add", str(WATCHLIST_PATH)], check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff.returncode != 0:
            subprocess.run(["git", "commit", "-m", "Update watchlist"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Pushed. GitHub Actions will alert your phone ~30 min before close.")
        else:
            print("Watchlist unchanged — no push needed.")
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Could not push watchlist: {e}")
        print("Run 'git push' manually to enable cloud alerts.")



if __name__ == "__main__":
    main()
