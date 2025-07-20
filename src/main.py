
import logging
import streamlit as st
import debugpy
from sqlalchemy.orm import joinedload

from sidebar_processor import update_sidebar, get_current_filters
from search_jobs import start_job_search
from display_jobs import process_results, show_jobs

from models_sql import init_db, Session, Job, Profile
from db_profiles import get_all_profiles, load_profile, save_profile, set_active_profile

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

init_db()

if "default" not in get_all_profiles():
    save_profile("default", filter_data=get_current_filters())
    set_active_profile("default")

st.set_page_config(page_title="Job-Genius", layout="wide")

st.title("🧠 Job-Genius: Smarter Job Search")

if "job_id_list" not in st.session_state:
    st.session_state["job_id_list"] = []

with st.sidebar:
    update_sidebar()

if st.session_state.get("show_favorites_pane"):

    st.header("⭐ Your Favorite Jobs")

    profile_name = st.session_state.get("selected_profile", "")
    if not profile_name:
        st.warning("Please select a profile to view favorites.")
    else:

        with Session() as db:

            profile = db.query(Profile).filter(Profile.name == profile_name).first()

            if not profile or not profile.favorite_job_ids:
                st.info("You haven't marked any jobs as favorite yet.")
            else:

                jobs = (
                    db.query(Job)
                    .options(joinedload(Job.company))
                    .filter(Job.job_id.in_(profile.favorite_job_ids))
                    .all()
                )

                show_jobs(jobs, key_prefix="fav")

        if st.button("⬅️ Back to Search", key="back_from_favorite"):
            st.session_state.show_favorites_pane = False
            st.rerun()

        st.divider()


if "llm_response" in st.session_state and st.session_state["llm_response"]:

    st.markdown("### 🤖 Assistant Response")
    st.markdown(st.session_state["llm_response"])

    if st.button("⬅️ Back to Search", key="back_from_llm_response"):
        st.session_state["llm_response"] = None
        st.rerun()

    st.divider()


# Search for jobs
if st.button("🚀 Search Jobs"):
    with st.spinner("Searching..."):
        st.session_state["llm_response"] = None
        start_job_search()

# Displaying jobs
if st.session_state["job_id_list"]:
    job_id_list = st.session_state["job_id_list"]
    s_profile = st.session_state.get("selected_profile", "default")
    profile_data = load_profile(s_profile)
    process_results(job_id_list, profile_data)

# if "debugger_active" not in st.session_state:
#     debugpy.listen(("0.0.0.0", 5678))
#     st.session_state["debugger_active"] = True
