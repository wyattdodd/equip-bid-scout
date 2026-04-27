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
    # Baby / infant
    "baby gate", "baby monitor", "baby swing", "baby bouncer", "baby carrier",
    "baby seat", "infant", "toddler", "stroller", "car seat", "pack n play",
    "diaper", "wipes",
    # Pets
    "dog", "cat", "puppy", "kitten", "pet bed", "pet crate", "bird cage",
    "fish tank", "aquarium", "litter box",
    # Phone/tablet accessories
    "holster", "belt clip", "phone pouch", "armband", "wrist strap",
    # Personal care junk
    "hair dryer", "hair straightener", "curling iron", "curling wand",
    "electric shaver", "epilator",
    # Toys / kids (not gaming)
    "action figure", "barbie", "lego set", "building blocks", "toy car",
    "board game", "puzzle",
    # Fitness accessories
    "yoga mat", "resistance band", "jump rope", "foam roller", "exercise band",
]

st.set_page_config(page_title="Settings — Equip-Bid Scout")
st.title("⚙️ Settings")

user_id = require_auth()
client = get_client()

result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
settings = result.data[0] if result.data else {}

# ── Location ──────────────────────────────────────────────────────────────────
st.subheader("Location")
city = st.text_input(
    "City filter",
    value=settings.get("city", "wichita"),
    help="Matched against auction location as a case-insensitive substring. 'wichita' matches 'Wichita, KS'.",
)

# ── What to Look For ──────────────────────────────────────────────────────────
st.subheader("What to look for")
st.caption("Items are ranked by estimated retail value. Only items matching at least one interest keyword are considered.")
interest_text = st.text_area(
    "Interest keywords — one per line",
    value="\n".join(settings.get("interest_keywords") or []),
    height=250,
    placeholder="dewalt\nlaptop\nsectional\nplaystation\n...",
    help="Any item whose title contains at least one of these words is included. Case-insensitive.",
)

# ── What to Filter Out ────────────────────────────────────────────────────────
st.subheader("What to filter out")
st.caption("Items matching any reject phrase are excluded even if they match an interest keyword. Use this to block accessories and junk results.")
saved_rejects = settings.get("reject_phrases")
reject_default = "\n".join(saved_rejects) if saved_rejects else "\n".join(DEFAULT_REJECT_PHRASES)
reject_text = st.text_area(
    "Reject phrases — one per line",
    value=reject_default,
    height=250,
    placeholder="couch cover\nparts only\nreplacement for\n...",
    help="If 'couch' is an interest keyword but you keep seeing couch covers, add 'couch cover' here.",
)

# ── Notifications ─────────────────────────────────────────────────────────────
st.subheader("Notifications")
with st.expander("How to set up ntfy.sh (free push notifications)"):
    st.markdown("""
1. Download the **ntfy** app on your phone ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
2. Open the app and tap **Subscribe to topic**
3. Enter any unique topic name — something only you'd guess, like `wyatt-auction-alerts-7x3`
4. Paste that same topic name below and save your settings
5. The GitHub Actions workflow will fire a push to your phone before each tracked auction closes
    """)

ntfy_topic = st.text_input(
    "ntfy.sh topic",
    value=settings.get("ntfy_topic") or "",
    placeholder="your-unique-topic-name",
    help="Must match the topic you subscribed to in the ntfy app.",
)

notify_minutes = st.slider(
    "Notify this many minutes before auction closes",
    min_value=10,
    max_value=60,
    value=settings.get("notify_minutes") or 30,
    help="30 minutes gives you time to decide and bid. 10 minutes is last-chance only.",
)

st.divider()
if st.button("Save Settings", type="primary", use_container_width=True):
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
