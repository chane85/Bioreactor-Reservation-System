import os
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
import auth
import _sandbox_server  # ensures backend is running before iframe loads

st.set_page_config(page_title="시뮬레이션", layout="wide")
auth.init_auth()
auth.enforce_idle_timeout()
auth.require_role('viewer')

st.markdown("""
    <style>
    .main .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    </style>
""", unsafe_allow_html=True)

# Append build mtime as cache-buster so the iframe always loads the latest build
_index = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', '..', 'sandbox_v2', 'frontend', 'dist', 'index.html')
_v    = str(int(os.path.getmtime(_index))) if os.path.exists(_index) else '1'
_user = urllib.parse.quote(auth.current_user() or '', safe='')

components.iframe(f"http://localhost:8565?v={_v}&user={_user}", height=1100, scrolling=True)
