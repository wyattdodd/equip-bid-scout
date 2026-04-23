from datetime import datetime, timezone, timedelta

BASE_URL = "https://www.equip-bid.com"


def _parse_closing_utc(utc_str: str | None) -> datetime | None:
    if not utc_str:
        return None
    try:
        clean = utc_str.replace(" UTC", "").strip()
        dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def build_ntfy_body(auction_id: str, items: list[dict]) -> str:
    if not items:
        raise ValueError(f"No items for auction {auction_id}")
    auction_title = items[0].get("auction_title", f"Auction {auction_id}")
    lines = [f"Auction: {auction_title}"]
    for item in items:
        title = item.get("title", "")[:60]
        bid = item.get("current_bid", "?")
        resale = item.get("est_resale", "?")
        lines.append(f"• {title}  |  Bid: {bid}  |  Est: {resale}")
    lines.append(f"{BASE_URL}/auction/{auction_id}")
    return "\n".join(lines)


def schedule_notifications(
    supabase_client,
    user_id: str,
    ntfy_topic: str,
    notify_minutes: int,
    flips: list[dict],
    tools: list[dict],
) -> int:
    supabase_client.table("scheduled_notifications")\
        .delete()\
        .eq("user_id", user_id)\
        .eq("notified", False)\
        .execute()

    all_picks = flips + tools
    if not all_picks:
        return 0

    auctions: dict[str, list[dict]] = {}
    for pick in all_picks:
        aid = pick.get("auction_id", "")
        if aid:
            auctions.setdefault(aid, []).append(pick)

    now = datetime.now(timezone.utc)
    rows = []

    for auction_id, picks in auctions.items():
        closing_dt = _parse_closing_utc(picks[0].get("closing_utc"))
        if not closing_dt:
            continue
        notify_at = closing_dt - timedelta(minutes=notify_minutes)
        if notify_at <= now:
            continue

        rows.append({
            "user_id": user_id,
            "auction_id": auction_id,
            "auction_title": picks[0].get("auction_title", ""),
            "ntfy_topic": ntfy_topic,
            "notify_at": notify_at.isoformat(),
            "items": [
                {
                    "title": p.get("title", ""),
                    "current_bid": p.get("current_bid", "$0.00"),
                    "est_resale": p.get("est_resale", "Unknown"),
                    "url": p.get("url", ""),
                    "auction_title": p.get("auction_title", ""),
                }
                for p in picks
            ],
        })

    if rows:
        supabase_client.table("scheduled_notifications").insert(rows).execute()

    return len(rows)
