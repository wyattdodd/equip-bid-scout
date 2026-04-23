#!/usr/bin/env python3
"""
equip_bid_scout.py
Scans equip-bid.com for tools, electronics, and furniture near Wichita, KS (67204).
Scores items by arbitrage potential using brand lookups and title parsing.
Runs entirely locally — no API calls, no tokens consumed.

Usage:
    py equip_bid_scout.py

Requires:
    pip install requests beautifulsoup4
"""

import datetime
import json
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.equip-bid.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$")
_LOCAL_FMT = "%m/%d/%Y %I:%M %p"   # e.g. "04/24/2026 07:05 pm"

# Auction location filter — any auction whose address contains one of these
# (case-insensitive) is considered nearby Wichita, KS
NEARBY_FILTER = [
    "wichita",
]

MAX_AUCTIONS = 10    # Auctions to scan per run
TOP_FLIPS = 5        # Max flip picks returned
TOP_TOOLS = 5        # Max tool picks returned (can be fewer if not found)
WATCHLIST_PATH = "watchlist.json"
# ──────────────────────────────────────────────────────────────────────────────

# ── Interest keywords (category pre-filter) ───────────────────────────────────
# Items whose title contains none of these words are skipped immediately.
# Words that disqualify a title even if it passes the interest keyword check.
# Catches accessories, replacement parts, and carry cases.
EXCLUSION_PHRASES = [
    # Phone/tablet accessories
    "case for", "case compatible", "compatible with", "replacement for",
    "adapter for", "charger for", "screen protector", "tempered glass",
    "silicone case", "phone case", "tablet case",
    "carrying case", "travel case", "hard case", "protective case",
    "cover for", "stand for", "holder for", "mount for",
    # Laptop accessories (not actual laptops)
    "laptop case", "laptop bag", "laptop backpack", "laptop sleeve",
    "laptop stand", "laptop riser", "laptop desk",
    # Furniture covers (not actual furniture)
    "couch cover", "sofa cover", "chair cover", "sectional cover",
    "slipcover", "slip cover", "furniture cover", "cushion cover",
    "cushion replacement", "upholstery foam",
    # Camera accessories and vehicle/baby cameras (not sellable electronics)
    "backup camera", "rear camera", "reverse camera", "dash cam",
    "baby camera", "baby monitor", "car camera", "parking camera",
    "camera strap", "camera bag", "lens cap",
    # Headphone/speaker accessories
    "headphone stand", "speaker stand", "earbud tips",
    # Replacement parts / accessories (not the actual item)
    "actuator", "rmt motor", "lift motor",
    "replacement legs", "furniture legs", "sofa legs", "couch legs",
    "rv seat", "seat cover", "outdoor cushion", "chair cushion",
    "patio cushion", "cushion set", "cushion replacement",
    # Condition flags
    "missing", "parts only", "for parts", "not working", "as is",
    "damaged", "cracked screen",
]

# Minimum resale value to bother recommending (filters out cheap flip-unworthy items)
MIN_RESALE_VALUE = 75.0

INTEREST_KEYWORDS = [
    # Power & hand tools
    "drill", "saw", "tool", "dewalt", "milwaukee", "makita", "ryobi",
    "craftsman", "wrench", "socket", "ratchet", "compressor", "welder",
    "grinder", "sander", "router", "impact", "circular", "jigsaw",
    "miter", "planer", "lathe", "workbench", "toolbox", "tool chest",
    "nail gun", "multimeter", "oscillating", "impact driver",
    # Electronics
    "tv", "television", "4k", "oled", "qled", "laptop", "computer",
    "ipad", "tablet", "iphone", "samsung", "speaker", "headphone",
    "airpod", "dslr", "mirrorless", "action camera", "4k camera",
    "playstation", "xbox", "nintendo", "switch",
    "monitor", "projector", "amplifier", "receiver", "subwoofer",
    "soundbar", "drone", "gopro", "kindle", "apple", "sony", "lg",
    "bose", "beats", "macbook", "chromebook", "graphics card",
    # Exercise / personal transport
    "treadmill", "walking pad", "scooter", "hoverboard", "elliptical",
    "stationary bike", "exercise bike",
    # Furniture
    "sofa", "couch", "chair", "recliner", "sectional", "ottoman",
    "desk", "dresser", "nightstand", "bed frame", "headboard",
    "dining table", "coffee table", "bookcase", "bookshelf", "cabinet",
    "armchair", "accent chair", "console", "credenza", "buffet",
    "side table", "bench", "bar stool", "patio furniture",
    "outdoor furniture", "teak", "restoration hardware", "pottery barn",
    "west elm", "ashley", "la-z-boy", "lazboy", "natuzzi",
    "ethan allen", "lane furniture", "bassett",
]

# Keywords that identify tools the user might personally want (subset of INTEREST_KEYWORDS).
# Items matching any of these go in the "For You — Tools" list instead of Flips.
TOOL_KEYWORDS = [
    "drill", "saw", "dewalt", "milwaukee", "makita", "ryobi",
    "craftsman", "wrench", "socket", "ratchet", "compressor", "welder",
    "grinder", "sander", "router", "impact driver", "impact wrench",
    "circular saw", "jigsaw", "miter saw", "planer", "lathe",
    "workbench", "toolbox", "tool chest", "nail gun", "multimeter",
    "oscillating tool", "oscillating multi",
]

# ── Brand / item value table ──────────────────────────────────────────────────
# Maps a keyword (found in item title) to an estimated (low, high) resale range
# in USD. Used when the title doesn't already say "Retails for $X".
BRAND_VALUE = {
    # Premium power tools
    "dewalt":               (80,   400),
    "milwaukee":            (100,  500),
    "makita":               (80,   350),
    "bosch":                (60,   300),
    "ridgid":               (60,   250),
    # Mid-range tools
    "ryobi":                (40,   200),
    "craftsman":            (30,   150),
    "black+decker":         (25,   120),
    "worx":                 (25,   100),
    # Apple devices
    "macbook":              (400, 1200),
    "ipad":                 (200,  800),
    "iphone":               (250,  900),
    "airpod":               (80,   250),
    "apple watch":          (150,  400),
    # Audio
    "bose":                 (100,  400),
    "beats":                (80,   300),
    "sony":                 (50,   350),
    "jbl":                  (40,   200),
    "sonos":                (150,  600),
    # TVs
    "oled":                 (400, 1800),
    "qled":                 (200, 1200),
    "television":           (100,  700),
    # Gaming
    "playstation 5":        (350,  500),
    "ps5":                  (350,  500),
    "xbox series":          (250,  450),
    "nintendo switch":      (150,  300),
    # Laptops
    "macbook":              (400, 1200),
    "laptop":               (150,  700),
    "chromebook":           (80,   300),
    # Cameras / drones — specific types only (vehicle/baby cameras filtered by exclusions)
    "dslr":                 (200, 1500),
    "mirrorless":           (300, 2000),
    "action camera":        (80,   400),
    "4k camera":            (100,  600),
    "drone":                (100,  600),
    "gopro":                (100,  400),
    # Speakers / headphones
    "headphone":            (40,   300),
    "subwoofer":            (80,   500),
    "soundbar":             (80,   400),
    "receiver":             (80,   500),
    "amplifier":            (80,   600),
    # Furniture brands
    "restoration hardware": (500, 3000),
    "pottery barn":         (200, 1200),
    "west elm":             (150,  900),
    "la-z-boy":             (200,  900),
    "lazboy":               (200,  900),
    "natuzzi":              (600, 2500),
    "ethan allen":          (300, 1800),
    "ashley":               (100,  600),
    # Generic furniture categories
    "sectional":            (250, 1200),
    "recliner":             (120,  600),
    "dresser":              (100,  500),
    "bookcase":             (60,   350),
    # Equipment
    "compressor":           (100,  600),
    "welder":               (120,  700),
    "generator":            (200, 1500),
}
# ──────────────────────────────────────────────────────────────────────────────


def _clean_picks(picks: list[dict]) -> list[dict]:
    return [
        {
            "title":         p.get("title", ""),
            "current_bid":   p.get("current_bid", "$0.00"),
            "est_resale":    p.get("_resale_est", "Unknown"),
            "closing":       p.get("closing", "Unknown"),
            "closing_utc":   p.get("closing_utc"),
            "url":           p.get("url", ""),
            "auction_id":    p.get("auction_id", ""),
            "auction_title": p.get("auction_title", ""),
        }
        for p in picks
    ]


def _save_watchlist_to(flips: list[dict], tools: list[dict], path: str) -> None:
    data = {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "flips": _clean_picks(flips),
        "tools": _clean_picks(tools),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_watchlist(flips: list[dict], tools: list[dict]) -> None:
    _save_watchlist_to(flips, tools, WATCHLIST_PATH)


def parse_dollar(text: str) -> float:
    m = re.search(r"\$?([\d,]+(?:\.\d+)?)", text.replace(",", ""))
    return float(m.group(1)) if m else 0.0


def extract_retail(title: str) -> float | None:
    """Pull stated retail price from title patterns like 'Retails for $X'."""
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
    """Return (low, high, brand_key) for the first brand match found in title."""
    t = title.lower()
    for brand, (lo, hi) in BRAND_VALUE.items():
        if brand in t:
            return lo, hi, brand
    return 0.0, 0.0, ""


def score_item(item: dict) -> float:
    """
    Score an item for arbitrage potential.
    Returns 0 if we can't estimate a resale value.
    Annotates item dict with _resale_est, _pct, _reason for display.
    """
    bid = parse_dollar(item["current_bid"])
    title = item["title"]

    retail = extract_retail(title)
    lo_resale, hi_resale, brand = lookup_brand(title)

    # Use stated retail first; fall back to brand table midpoint
    if retail and retail > 0:
        if retail < MIN_RESALE_VALUE:
            return 0.0  # Not worth the effort to flip
        ref = retail
        item["_resale_est"] = f"~${retail:.0f} (stated retail)"
    elif lo_resale > 0:
        ref = (lo_resale + hi_resale) / 2
        item["_resale_est"] = f"${lo_resale:.0f}-${hi_resale:.0f} (brand: {brand})"
    else:
        return 0.0

    if ref < MIN_RESALE_VALUE:
        return 0.0

    # Effective bid for ratio (treat $0 as $1 so it doesn't break math)
    effective_bid = bid if bid > 0 else 1.0
    pct = effective_bid / ref
    item["_pct"] = pct
    item["_ref"] = ref

    if pct >= 0.70:
        return 0.0  # Too close to resale to be interesting

    # Score: higher when bid is a smaller fraction of resale value
    base = (1.0 - pct) * 100

    # Bonus for $0 starting bid — hasn't been touched yet
    if bid == 0:
        base += 25

    # Bonus for very deep discount
    if pct < 0.20:
        base += 20

    return base


def _parse_closing_span(span) -> tuple[str, str | None]:
    """Extract (closing_display, closing_utc) from a BeautifulSoup timer span.

    Tries the span title attribute first (ideal: 'YYYY-MM-DD HH:MM:SS UTC').
    Falls back to parsing the display text as local time ('MM/DD/YYYY HH:MM am/pm').
    Returns (display_text, closing_utc_str) where closing_utc_str is None if unparseable.
    """
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


def get_nearby_auctions() -> list[dict]:
    """Scrape /auction/list and return auctions near Wichita, KS."""
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

        # Walk up the DOM to find the enclosing .row card
        row = title_span
        for _ in range(6):
            row = row.parent
            if row and "row" in (row.get("class") or []):
                break

        # Location text — in the div that holds the globe icon
        location_text = ""
        for i_tag in row.find_all("i"):
            if "globe" in " ".join(i_tag.get("class") or []):
                location_text = i_tag.parent.get_text(strip=True)
                break

        # Closing time — display text + UTC datetime from span title attribute
        closing = "Unknown"
        closing_utc = None
        timer_div = row.find("div", class_="auction-listing-timer")
        if timer_div:
            span = timer_div.find("span", title=lambda t: t and "UTC" in t)
            if span:
                closing, closing_utc = _parse_closing_span(span)

        if not any(kw in location_text.lower() for kw in NEARBY_FILTER):
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


def get_auction_items(auction_id: str, auction_closing: str, auction_closing_utc: str | None = None) -> list[dict]:
    """Scrape all lots from one auction page, pre-filtering by interest keywords."""
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

        # Skip items outside our interest categories
        title_lower = title.lower()
        if not any(kw in title_lower for kw in INTEREST_KEYWORDS):
            continue

        # Skip accessories, cases, replacement parts, etc.
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


def _is_tool(item: dict) -> bool:
    t = item["title"].lower()
    return any(kw in t for kw in TOOL_KEYWORDS)


def _print_section(header: str, picks: list[dict]) -> None:
    print("=" * 68)
    print(f"   {header}")
    print("=" * 68)
    if not picks:
        print("  (none found this run)")
    for i, p in enumerate(picks, 1):
        pct_line = f"  ({p['_pct'] * 100:.0f}% of resale)" if "_pct" in p else ""
        print(f"\n#{i}  {p['title'][:78]}")
        print(f"    Current Bid:   {p['current_bid']}")
        print(f"    Est. Resale:   {p.get('_resale_est', 'Unknown')}{pct_line}")
        print(f"    Closes:        {p['closing']}")
        print(f"    Link:          {p['url']}")
    print()


def main():
    print("Scanning Equip-Bid for arbitrage opportunities near Wichita, KS...\n")

    auctions = get_nearby_auctions()
    if not auctions:
        print("No nearby auctions found. The site may be down or page structure changed.")
        return

    print(f"Found {len(auctions)} nearby auctions. Scanning lots...\n")

    all_items: list[dict] = []
    for a in auctions:
        try:
            items = get_auction_items(a["id"], a["closing"], a.get("closing_utc"))
            for item in items:
                item["auction_id"] = a["id"]
                item["auction_title"] = a["title"]
            all_items.extend(items)
            print(
                f"  {a['location']:<42} "
                f"{len(items):>3} matching lots  |  closes {a['closing']}"
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"  [skipped] {a['title'][:55]}  ({e})")

    if not all_items:
        print("\nNo items matched your interest categories.")
        print("Try adding more keywords to INTEREST_KEYWORDS in the script.")
        return

    # Score every item; keep those with a positive score
    scored = []
    for item in all_items:
        s = score_item(item)
        if s > 0:
            scored.append((s, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Split into tools (personal interest) and everything else (flips)
    tool_scored = [(s, it) for s, it in scored if _is_tool(it)]
    flip_scored = [(s, it) for s, it in scored if not _is_tool(it)]

    tool_picks = [it for _, it in tool_scored[:TOP_TOOLS]]
    flip_picks = [it for _, it in flip_scored[:TOP_FLIPS]]

    print(
        f"\nAnalyzed {len(all_items)} relevant items, "
        f"{len(scored)} with estimable resale value "
        f"({len(tool_scored)} tools, {len(flip_scored)} flips).\n"
    )

    _print_section("TOP FLIPS — EQUIP-BID NEAR WICHITA, KS", flip_picks)
    _print_section("FOR YOU — TOOLS", tool_picks)

    save_watchlist(flip_picks, tool_picks)
    print(f"Watchlist saved to {WATCHLIST_PATH}")
    print("Run 'py main.py' to review picks and push to GitHub for cloud alerts.")


if __name__ == "__main__":
    main()
