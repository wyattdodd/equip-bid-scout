import streamlit as st
from services.supabase_client import get_client, require_auth

st.set_page_config(page_title="Dashboard — Equip-Bid Scout")
st.title("Dashboard")

user_id = require_auth()
client = get_client()

st.markdown(f"Logged in as **{st.session_state.get('user_email', '')}**")
st.divider()

st.subheader("Last Run")
runs = (
    client.table("watchlist_runs")
    .select("generated_at, flips, tools")
    .eq("user_id", user_id)
    .order("generated_at", desc=True)
    .limit(1)
    .execute()
)

if runs.data:
    run = runs.data[0]
    flips = run.get("flips") or []
    tools = run.get("tools") or []
    from datetime import datetime, timezone
    ts = datetime.fromisoformat(run["generated_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    st.markdown(f"**{ts} UTC** — {len(flips)} flip(s), {len(tools)} tool(s) found")
else:
    st.write("No runs yet.")

st.divider()

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
        from datetime import datetime
        notify_time = datetime.fromisoformat(row["notify_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        title = (row.get("auction_title") or row["auction_id"])[:60]
        st.markdown(f"- **{title}** — notify at {notify_time} UTC")
else:
    st.write("No pending notifications. Run the scout to schedule some.")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/3_Run_Tool.py", label="Run Scout →")
with col2:
    st.page_link("pages/2_Settings.py", label="Settings →")
