import streamlit as st
from services.supabase_client import get_client, require_auth

st.set_page_config(page_title="Settings — Equip-Bid Scout")
st.title("Settings")

user_id = require_auth()
client = get_client()

result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
settings = result.data[0] if result.data else {}

city = st.text_input(
    "City filter",
    value=settings.get("city", "wichita"),
    help="Case-insensitive substring matched against auction location (e.g. 'wichita')",
)

interest_text = st.text_area(
    "Interest keywords — one per line",
    value="\n".join(settings.get("interest_keywords") or []),
    height=250,
    help="Items whose title contains none of these are skipped",
)

tool_text = st.text_area(
    "Tool keywords — one per line",
    value="\n".join(settings.get("tool_keywords") or []),
    height=150,
    help="Items matching any of these go in the Tools section instead of Flips",
)

ntfy_topic = st.text_input(
    "ntfy.sh topic",
    value=settings.get("ntfy_topic") or "",
    help="Open the ntfy app → Subscribe → enter this value. Pick something unique.",
)

notify_minutes = st.slider(
    "Notify X minutes before auction closes",
    min_value=10,
    max_value=60,
    value=settings.get("notify_minutes") or 30,
)

if st.button("Save Settings", type="primary"):
    interest_keywords = [kw.strip() for kw in interest_text.splitlines() if kw.strip()]
    tool_keywords = [kw.strip() for kw in tool_text.splitlines() if kw.strip()]
    res = client.table("user_settings").upsert({
        "user_id": user_id,
        "city": city.strip().lower(),
        "interest_keywords": interest_keywords,
        "tool_keywords": tool_keywords,
        "ntfy_topic": ntfy_topic.strip(),
        "notify_minutes": notify_minutes,
    }).execute()
    if res.data:
        st.success("Settings saved.")
    else:
        st.error("Failed to save settings. Please try again.")
