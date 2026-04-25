import streamlit as st
from services.supabase_client import get_client, require_auth
from services.scout import run_scout
from services.notifications import schedule_notifications

st.set_page_config(page_title="Run Scout — Equip-Bid Scout")
st.title("🔍 Run Scout")

user_id = require_auth()
client = get_client()

result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
if not result.data:
    st.warning("No settings found. Set up your keywords before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

settings = result.data[0]

if not settings.get("interest_keywords"):
    st.warning("No interest keywords configured. Add them in Settings before running.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

if not settings.get("ntfy_topic"):
    st.warning("ntfy.sh topic not set. Add it in Settings to receive notifications.")
    st.page_link("pages/2_Settings.py", label="Go to Settings →")
    st.stop()

with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    col1.metric("City", settings.get("city", "—").title())
    col2.metric("Keywords", len(settings.get("interest_keywords") or []))
    col3.metric("Notify", f"{settings.get('notify_minutes', 30)} min before close")

st.caption(f"ntfy topic: **{settings['ntfy_topic']}**")

st.info(
    "The scout fetches up to 10 auctions near your city, filters items by your keywords, "
    "removes anything matching your reject phrases, and returns the 10 highest estimated-value items. "
    "Takes 30–60 seconds."
)

if st.button("Run Scout", type="primary", use_container_width=True):
    with st.spinner("Scanning equip-bid.com..."):
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
        st.warning(
            "No results found. Try adding more interest keywords or check that auctions are "
            "currently active near your city."
        )
    else:
        for p in picks:
            with st.container(border=True):
                st.markdown(f"**{p['title'][:80]}**")
                col1, col2, col3 = st.columns([1, 1, 2])
                col1.markdown(f"**Bid:** `{p['current_bid']}`")
                col2.markdown(f"**Est:** `{p['est_resale'].split(' (')[0]}`")
                col3.markdown(f"**Closes:** {p['closing']}")
                st.markdown(f"[View on Equip-Bid →]({p['url']})")

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

    st.success(
        f"Done. {count} auction notification(s) scheduled to your ntfy topic **{settings['ntfy_topic']}**."
    )
