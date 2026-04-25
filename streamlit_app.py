import streamlit as st
from services.supabase_client import get_client

st.set_page_config(page_title="Equip-Bid Scout", page_icon="🔍", layout="centered")
st.title("🔍 Equip-Bid Scout")
st.caption("Finds the highest-value auction items near you and sends push notifications before they close.")

if st.session_state.get("access_token"):
    st.success(f"Logged in as {st.session_state.get('user_email', '')}")
    col1, col2 = st.columns(2)
    with col1:
        st.page_link("pages/1_Dashboard.py", label="Go to Dashboard →")
    with col2:
        if st.button("Log out", use_container_width=True):
            client = get_client()
            client.auth.sign_out()
            for key in ["access_token", "refresh_token", "user_id", "user_email", "supabase_client"]:
                st.session_state.pop(key, None)
            st.rerun()
else:
    with st.expander("How it works", expanded=False):
        st.markdown("""
1. **Set your interests** — enter keywords like `dewalt`, `laptop`, `sectional` in Settings
2. **Run the scout** — it scans equip-bid.com auctions near your city and ranks the 10 highest-value matching items
3. **Get notified** — the app schedules a push notification via [ntfy.sh](https://ntfy.sh) before each auction closes

**To receive notifications on your phone:**
- Install the [ntfy app](https://ntfy.sh) (free, iOS & Android)
- In Settings, enter any unique topic name (e.g. `wyatt-equip-scout`)
- Subscribe to that topic in the ntfy app
        """)

    st.divider()

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Log In", type="primary", use_container_width=True):
            try:
                client = get_client()
                resp = client.auth.sign_in_with_password({"email": email, "password": password})
                if resp.session is None:
                    st.error("Login failed: email confirmation may be required. Check your inbox.")
                else:
                    st.session_state.access_token = resp.session.access_token
                    st.session_state.refresh_token = resp.session.refresh_token
                    st.session_state.user_id = resp.user.id
                    st.session_state.user_email = resp.user.email
                    st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

        st.divider()
        reset_email = st.text_input("Email for password reset", key="reset_email")
        if st.button("Send Password Reset Email", use_container_width=True):
            try:
                get_client().auth.reset_password_email(reset_email)
                st.success("Reset email sent. Check your inbox.")
            except Exception as e:
                st.error(f"Failed: {e}")

    with tab_signup:
        st.info("Create an account to get started. No email confirmation required.")
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password (min 6 characters)", type="password", key="signup_password")
        if st.button("Create Account", type="primary", use_container_width=True):
            try:
                get_client().auth.sign_up({"email": new_email, "password": new_password})
                st.success("Account created! Switch to the Log In tab to sign in.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")
