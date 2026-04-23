"""
services/supabase_client.py
Supabase client factory and authentication guard for use by all Streamlit pages.
"""

import streamlit as st
from supabase import create_client, Client


def get_client() -> Client:
    client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
    return client


def require_auth() -> str:
    """Returns user_id if authenticated, otherwise stops page rendering."""
    if not st.session_state.get("access_token"):
        st.warning("Please log in to continue.")
        st.page_link("streamlit_app.py", label="Go to Login →")
        st.stop()
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.warning("Session expired. Please log in again.")
        st.page_link("streamlit_app.py", label="Go to Login →")
        st.stop()
    return user_id
