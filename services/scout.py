#!/usr/bin/env python3
"""
services/scout.py
Scrapes equip-bid.com and returns the top items by estimated retail value.
All per-user config (city, keywords, reject phrases) is passed as parameters.
"""

import datetime
import re
import time
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.equip-bid.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$")
_LOCAL_FMT = "%m/%d/%Y %I:%M %p"

TOP_PICKS = 10
MIN_RESALE_VALUE = 75.0
# Items with a stated retail but NO recognizable brand need a higher bar —
# this blocks cheap junk (baby gates, phone holsters) that auction descriptions
# price up with unrealistic MSRPs.
MIN_STATED_RETAIL_NO_BRAND = 150.0

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


def _get_ref(item: dict) -> float:
    """Compute estimated retail value; sets item['_resale_est'] as a side effect."""
    title = item["title"]
    retail = extract_retail(title)
    lo, hi, brand = lookup_brand(title)
    if retail:
        threshold = MIN_RESALE_VALUE if brand else MIN_STATED_RETAIL_NO_BRAND
        if retail >= threshold:
            item["_resale_est"] = f"~${retail:.0f} (stated retail)"
            return retail
    if lo > 0:
        ref = (lo + hi) / 2
        item["_resale_est"] = f"${lo:.0f}-${hi:.0f} (brand: {brand})"
        return ref
    return 0.0


def _parse_closing_span(span) -> tuple[str, str | None]:
    closing = span.get_text(strip=True)
    raw = span.get("title", "").strip()
    if _UTC_RE.match(raw):
        return closing, raw
    try:
        dt = datetime.datetime.strptime(closing, _LOCAL_FMT)
        dt_utc = dt.replace(tzinfo=ZoneInfo("America/Chicago")).astimezone(datetime.timezone.utc)
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


def get_nearby_auctions(city_filter: list[str]) -> list[dict]:
    auctions = []
    seen_ids: set[str] = set()
    page = 1

    while page <= 20:
        params = {"page": page} if page > 1 else None
        resp = requests.get(f"{BASE_URL}/auction/list", headers=HEADERS, timeout=15, params=params)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        found_on_page = 0
        for title_span in soup.select("span.auction-title.description-wrap-fix"):
            link = title_span.find("a")
            if not link:
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)

            m = re.search(r"/auction/(\d+)", href)
            if not m or m.group(1) in seen_ids:
                continue

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

            if not any(kw in location_text.lower() for kw in city_filter):
                continue

            closing = "Unknown"
            closing_utc = None
            timer_div = row.find("div", class_="auction-listing-timer")
            if timer_div:
                span = timer_div.find("span", title=lambda t: t and "UTC" in t)
                if span:
                    closing, closing_utc = _parse_closing_span(span)

            auction_id = m.group(1)
            seen_ids.add(auction_id)
            found_on_page += 1
            auctions.append({
                "id": auction_id,
                "title": title[:90],
                "location": location_text,
                "closing": closing,
                "closing_utc": closing_utc,
                "url": f"{BASE_URL}{href}",
            })

        if found_on_page == 0:
            break

        next_link = (
            soup.select_one("a[rel='next']")
            or soup.select_one("li.next:not(.disabled) a")
            or soup.select_one(".pagination a[aria-label='Next']")
        )
        if not next_link:
            break

        page += 1
        time.sleep(0.3)

    return auctions


def get_auction_items(
    auction_id: str,
    auction_closing: str,
    interest_keywords: list[str],
    reject_phrases: list[str],
    auction_closing_utc: str | None = None,
) -> list[dict]:
    items = []
    page = 1

    while page <= 20:
        params = {"page": page} if page > 1 else None
        resp = requests.get(
            f"{BASE_URL}/auction/{auction_id}", headers=HEADERS, timeout=20, params=params
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        found_on_page = 0
        for h4 in soup.find_all("h4", id=lambda x: x and x.startswith("itemTitle")):
            link = h4.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            title_lower = title.lower()

            if not any(kw in title_lower for kw in interest_keywords):
                continue
            if any(phrase in title_lower for phrase in reject_phrases):
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
            found_on_page += 1

        if found_on_page == 0:
            break

        next_link = (
            soup.select_one("a[rel='next']")
            or soup.select_one("li.next:not(.disabled) a")
            or soup.select_one(".pagination a[aria-label='Next']")
        )
        if not next_link:
            break

        page += 1
        time.sleep(0.3)

    return items


def run_scout(
    city_filter: list[str],
    interest_keywords: list[str],
    reject_phrases: list[str],
) -> dict:
    """Scrape equip-bid.com and return the top 10 items by estimated retail value."""
    auctions = get_nearby_auctions(city_filter)
    if not auctions:
        return {"picks": [], "errors": 0}

    all_items: list[dict] = []
    error_count = 0
    for a in auctions:
        try:
            items = get_auction_items(
                a["id"], a["closing"], interest_keywords, reject_phrases, a.get("closing_utc")
            )
            for item in items:
                item["auction_id"] = a["id"]
                item["auction_title"] = a["title"]
            all_items.extend(items)
            time.sleep(0.5)
        except Exception as exc:
            print(f"[WARN] Skipping auction {a['id']}: {exc}")
            error_count += 1

    valued = []
    for item in all_items:
        ref = _get_ref(item)
        if ref >= MIN_RESALE_VALUE:
            valued.append((ref, item))
    valued.sort(key=lambda x: x[0], reverse=True)

    return {
        "picks": [_clean_pick(it) for _, it in valued[:TOP_PICKS]],
        "errors": error_count,
    }
