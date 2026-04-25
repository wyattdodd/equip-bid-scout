import streamlit as st
from services.supabase_client import get_client, require_auth

DEFAULT_REJECT_PHRASES = [
    "case for", "case compatible", "compatible with", "replacement for",
    "adapter for", "charger for", "screen protector", "tempered glass",
    "silicone case", "phone case", "tablet case",
    "carrying case", "travel case", "hard case", "protective case",
    "cover for", "stand for", "holder for", "mount for",
    "laptop case", "laptop bag", "laptop backpack", "laptop sleeve",
    "laptop stand", "laptop riser", "laptop desk",
    "couch cover", "sofa cover", "chair cover", "sectional cover",
    "slipcover", "slip cover", "furniture cover", "cushion cover",
    "cushion replacement", "upholstery foam",
    "backup camera", "rear camera", "reverse camera", "dash cam",
    "baby camera", "baby monitor", "car camera", "parking camera",
    "camera strap", "camera bag", "lens cap",
    "headphone stand", "speaker stand", "earbud tips",
    "actuator", "rmt motor", "lift motor",
    "replacement legs", "furniture legs", "sofa legs", "couch legs",
    "rv seat", "seat cover", "outdoor cushion", "chair cushion",
    "patio cushion", "cushion set",
    "missing", "parts only", "for parts", "not working", "as is",
    "damaged", "cracked screen",
]

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

saved_rejects = settings.get("reject_phrases")
reject_default = "\n".join(saved_rejects) if saved_rejects else "\n".join(DEFAULT_REJECT_PHRASES)
reject_text = st.text_area(
    "Reject phrases — one per line",
    value=reject_default,
    height=250,
    help="Items whose title contains any of these are excluded (e.g. 'couch cover' to block accessories when searching for 'couch')",
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
    reject_phrases = [p.strip() for p in reject_text.splitlines() if p.strip()]
    res = client.table("user_settings").upsert({
        "user_id": user_id,
        "city": city.strip().lower(),
        "interest_keywords": interest_keywords,
        "reject_phrases": reject_phrases,
        "ntfy_topic": ntfy_topic.strip(),
        "notify_minutes": notify_minutes,
    }).execute()
    if res.data:
        st.success("Settings saved.")
    else:
        st.error("Failed to save settings. Please try again.")
