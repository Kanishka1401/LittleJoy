"""Little Joys · Creator Intelligence Platform – Streamlit front-end.   Run:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Little Joys · Creator Intelligence", page_icon="●", layout="wide", initial_sidebar_state="collapsed")

from dashboard import data as D                       # noqa: E402
from dashboard import theme                           # noqa: E402
from dashboard import (views_ads, views_creators, views_method, views_overview, views_rankings, views_dna, views_studio, views_home)  # noqa: E402

PAGES = {
    "Home": views_home.render,
    "Overview": views_overview.render,
    "Creator shortlist": views_rankings.render,
    "Creator profiles": views_creators.render,
    "Ad intelligence": views_ads.render,
    "Creative DNA": views_dna.render,
    "Campaign Studio": views_studio.render,
    "Methodology": views_method.render,
}

st.markdown(theme.CSS, unsafe_allow_html=True)

brand_col, nav_col = st.columns([1, 3.6], vertical_alignment="center", gap="large")
brand_col.markdown(theme.BRAND_HTML, unsafe_allow_html=True)
page = nav_col.radio("Navigate", list(PAGES), horizontal=True, label_visibility="collapsed", key="nav")

if not D.outputs_ready():
    st.error("Engine outputs not found. Run `python scripts/run_ad_analysis.py` and `python scripts/run_creator_analysis.py` first.")
    st.stop()

PAGES[page]()
st.markdown(theme.colophon(), unsafe_allow_html=True)
