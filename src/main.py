
import logging
import streamlit as st
import debugpy

from sidebar_processor import update_sidebar, get_current_filters
from search_jobs import start_job_search
from display_jobs import process_results

from models_sql import init_db
from db_profiles import get_all_profiles, load_profile, save_profile

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

init_db()

if "default" not in get_all_profiles():
    save_profile("default", filter_data=get_current_filters())

st.set_page_config(page_title="Job-Genius", layout="wide")

st.title("🧠 Job-Genius: Smarter Job Search")

if "result_list" not in st.session_state:
    st.session_state["result_list"] = []

with st.sidebar:
    update_sidebar()

if st.button("🚀 Search Jobs"):
    with st.spinner("Searching..."):
        st.session_state["llm_response"] = None
        start_job_search()

if st.session_state["result_list"]:
    selected_profile = st.session_state.get("selected_profile", "default")
    profile_data = load_profile(selected_profile)
    process_results(st.session_state["result_list"], profile_data)

# if "debugger_active" not in st.session_state:
#     debugpy.listen(("0.0.0.0", 5678))
#     st.session_state["debugger_active"] = True
