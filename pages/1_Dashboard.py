from datetime import datetime

import streamlit as st
from services.supabase_client import get_client, require_auth


def _fmt_ts(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%b %d, %Y %H:%M")


def _delete_pick(client, user_id: str, run_id: str, removed: dict, remaining: list[dict]) -> None:
    client.table("watchlist_runs").update({"flips": remaining}).eq("id", run_id).execute()

    auction_id = removed.get("auction_id", "")
    if not auction_id:
        return

    still_in_auction = [p for p in remaining if p.get("auction_id") == auction_id]

    if not still_in_auction:
        client.table("scheduled_notifications") \
            .delete() \
            .eq("user_id", user_id) \
            .eq("auction_id", auction_id) \
            .eq("notified", False) \
            .execute()
    else:
        result = client.table("scheduled_notifications") \
            .select("id, items") \
            .eq("user_id", user_id) \
            .eq("auction_id", auction_id) \
            .eq("notified", False) \
            .execute()
        if result.data:
            notif = result.data[0]
            removed_url = removed.get("url", "")
            updated_items = [it for it in (notif["items"] or []) if it.get("url") != removed_url]
            client.table("scheduled_notifications") \
                .update({"items": updated_items}) \
                .eq("id", notif["id"]) \
                .execute()


st.set_page_config(page_title="Dashboard — Equip-Bid Scout")
st.title("Dashboard")
st.caption(f"Logged in as {st.session_state.get('user_email', '')}")

user_id = require_auth()
client = get_client()

# ── Last Run ──────────────────────────────────────────────────────────────────
st.subheader("Last Run")
runs = (
    client.table("watchlist_runs")
    .select("id, generated_at, flips")
    .eq("user_id", user_id)
    .order("generated_at", desc=True)
    .limit(1)
    .execute()
)

if runs.data:
    run = runs.data[0]
    run_id = run["id"]
    state_key = f"picks_{run_id}"

    if state_key not in st.session_state:
        st.session_state[state_key] = run.get("flips") or []

    picks = st.session_state[state_key]
    ts = _fmt_ts(run["generated_at"])
    st.markdown(f"**{ts} UTC** — {len(picks)} pick(s) found")

    if picks:
        for i, p in enumerate(picks):
            with st.container(border=True):
                col_main, col_del = st.columns([12, 1])
                with col_main:
                    st.markdown(f"**{p.get('title', '')[:80]}**")
                    col1, col2, col3 = st.columns([1, 1, 2])
                    col1.markdown(f"Bid: `{p.get('current_bid', '?')}`")
                    col2.markdown(f"Est: `{p.get('est_resale', '?').split(' (')[0]}`")
                    col3.markdown(f"Closes: {p.get('closing', '?')}")
                    st.markdown(f"[View on Equip-Bid →]({p.get('url', '')})")
                with col_del:
                    if st.button("🗑️", key=f"del_{run_id}_{i}", help="Remove this item"):
                        remaining = [x for j, x in enumerate(st.session_state[state_key]) if j != i]
                        st.session_state[state_key] = remaining
                        _delete_pick(client, user_id, run_id, p, remaining)
                        st.rerun()
    else:
        st.info("All items removed. Run the scout again to find new picks.")
else:
    st.info("No runs yet. Head to **Run Scout** to scan for items.")

st.divider()

# ── Upcoming Notifications ────────────────────────────────────────────────────
st.subheader("Upcoming Notifications")
pending = (
    client.table("scheduled_notifications")
    .select("auction_title, notify_at, auction_id")
    .eq("user_id", user_id)
    .eq("notified", False)
    .order("notify_at")
    .execute()
)

if pending.data:
    for row in pending.data:
        notify_time = _fmt_ts(row["notify_at"])
        title = (row.get("auction_title") or row["auction_id"])[:60]
        st.markdown(f"- **{title}** — notify at {notify_time} UTC")
else:
    st.info("No pending notifications. Run the scout to schedule some.")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/3_Run_Tool.py", label="🔍 Run Scout")
with col2:
    st.page_link("pages/2_Settings.py", label="⚙️ Settings")
