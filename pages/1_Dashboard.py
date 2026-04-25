from datetime import datetime

import streamlit as st
from services.supabase_client import get_client, require_auth


def _fmt_ts(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%b %d, %Y %H:%M")


st.set_page_config(page_title="Dashboard — Equip-Bid Scout")
st.title("Dashboard")
st.caption(f"Logged in as {st.session_state.get('user_email', '')}")

user_id = require_auth()
client = get_client()

# ── Last Run ──────────────────────────────────────────────────────────────────
st.subheader("Last Run")
runs = (
    client.table("watchlist_runs")
    .select("generated_at, flips")
    .eq("user_id", user_id)
    .order("generated_at", desc=True)
    .limit(1)
    .execute()
)

if runs.data:
    run = runs.data[0]
    picks = run.get("flips") or []
    ts = _fmt_ts(run["generated_at"])
    st.markdown(f"**{ts} UTC** — {len(picks)} pick(s) found")

    if picks:
        for p in picks:
            with st.container(border=True):
                st.markdown(f"**{p.get('title', '')[:80]}**")
                col1, col2, col3 = st.columns([1, 1, 2])
                col1.markdown(f"Bid: `{p.get('current_bid', '?')}`")
                col2.markdown(f"Est: `{p.get('est_resale', '?').split(' (')[0]}`")
                col3.markdown(f"Closes: {p.get('closing', '?')}")
                st.markdown(f"[View on Equip-Bid →]({p.get('url', '')})")
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
