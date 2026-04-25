import streamlit as st
from services.supabase_client import get_client, require_auth
from services.scout import run_scout
from services.notifications import schedule_notifications

st.set_page_config(page_title="Run Tool — Equip-Bid Scout")
st.title("Run Scout")

user_id = require_auth()
client = get_client()

result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
if not result.data:
    st.warning("No settings found. Configure your settings before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

settings = result.data[0]

if not settings.get("ntfy_topic"):
    st.warning("ntfy.sh topic not set. Add it in Settings before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

if not settings.get("interest_keywords"):
    st.warning("No interest keywords configured. Add them in Settings before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

st.caption(f"City: **{settings.get('city', '')}** | ntfy topic: **{settings['ntfy_topic']}** | Notify **{settings.get('notify_minutes', 30)} min** before close")

if st.button("Run Scout", type="primary"):
    with st.spinner("Scanning equip-bid.com — this takes 30–60 seconds..."):
        try:
            results = run_scout(
                city_filter=[settings.get("city", "")],
                interest_keywords=settings["interest_keywords"],
                reject_phrases=settings.get("reject_phrases") or [],
            )
        except Exception as e:
            st.error(f"Scout failed: {e}")
            st.stop()

    picks = results.get("picks", [])
    if results.get("errors"):
        st.warning(f"{results['errors']} auction(s) failed to scrape and were skipped.")

    st.subheader(f"Top Picks — {len(picks)} found")
    if not picks:
        st.write("No results found this run. Try broadening your interest keywords.")
    for p in picks:
        st.markdown(f"**{p['title'][:80]}**")
        st.markdown(
            f"Bid: `{p['current_bid']}` &nbsp;|&nbsp; Est: `{p['est_resale']}` &nbsp;|&nbsp; Closes: {p['closing']}"
        )
        st.markdown(f"[View item →]({p['url']})")
        st.divider()

    client.table("watchlist_runs").insert({
        "user_id": user_id,
        "flips": picks,
        "tools": [],
    }).execute()

    count = schedule_notifications(
        client,
        user_id,
        settings["ntfy_topic"],
        settings.get("notify_minutes") or 30,
        picks,
    )

    st.success(f"Run complete. {count} auction notification(s) scheduled.")
