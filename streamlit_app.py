import streamlit as st
from services.supabase_client import get_client

st.set_page_config(page_title="Equip-Bid Scout", page_icon="🔍", layout="centered")
st.title("Equip-Bid Scout")

if st.session_state.get("access_token"):
    st.success(f"Logged in as {st.session_state.get('user_email', '')}")
    if st.button("Log out"):
        get_client().auth.sign_out()
        for key in ["access_token", "refresh_token", "user_id", "user_email"]:
            st.session_state.pop(key, None)
        st.rerun()
    st.page_link("pages/1_Dashboard.py", label="Go to Dashboard →")
else:
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Log In"):
            try:
                client = get_client()
                resp = client.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.access_token = resp.session.access_token
                st.session_state.refresh_token = resp.session.refresh_token
                st.session_state.user_id = resp.user.id
                st.session_state.user_email = resp.user.email
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

        st.divider()
        reset_email = st.text_input("Email for password reset", key="reset_email")
        if st.button("Send Password Reset Email"):
            try:
                get_client().auth.reset_password_email(reset_email)
                st.success("Reset email sent. Check your inbox.")
            except Exception as e:
                st.error(f"Failed: {e}")

    with tab_signup:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password (min 6 characters)", type="password", key="signup_password")
        if st.button("Create Account"):
            try:
                get_client().auth.sign_up({"email": new_email, "password": new_password})
                st.success("Account created. Log in with your credentials above.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")
