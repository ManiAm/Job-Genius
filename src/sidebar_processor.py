
import time
import math
import re
import streamlit as st
import pydeck as pdk
from nominatim_api import get_coordinates
from sqlalchemy import delete

import config
from models_sql import Session, Job, JobEmbedding
from locale_utils import get_countries, get_languages
from db_profiles import get_all_profiles, load_profile, save_profile, set_active_profile, get_active_profile, clear_resume
from models_redis import redis_client
from job_embedder import summarize_and_embed
from chat_llm import send_prompt_to_llm
from resume_summarize import summarize_resume


employment_type_options = {
    "Full Time"  : "FULLTIME",
    "Part Time"  : "PARTTIME",
    "Contractor" : "CONTRACTOR",
    "Internship" : "INTERN"
}

experience_options = {
    "Less than 3 years"      : "under_3_years_experience",
    "More than 3 years"      : "more_than_3_years_experience",
    "No Experience Required" : "no_experience",
    "No Degree Required"     : "no_degree"
}


def update_sidebar():

    st.header("👤 Profile")

    all_profiles = get_all_profiles()

    if not all_profiles:
        st.error("No user profile found!")
        sys.exit(1)

    active_profile_name = get_active_profile()
    active_profile_index = all_profiles.index(active_profile_name)

    st.selectbox(
        "Select Profile",
        options=all_profiles,
        index=active_profile_index,
        key="selected_profile",
        on_change=profile_change_callback
    )

    st.text_input(
        "Create New Profile",
        placeholder="Enter name and press Enter",
        key="profile_name",
        on_change=create_profile_callback
    )

    profile_data = load_profile(active_profile_name)

    ##############

    st.sidebar.header("⭐ Favorites")

    if "show_favorites_pane" not in st.session_state:
        st.session_state.show_favorites_pane = False

    if st.sidebar.button("📝 View Favorite Jobs"):
        st.session_state.show_favorites_pane = True

    ##############

    st.header("📍 Location")

    my_location = profile_data.get("my_location", None)

    my_location = st.text_input(
        "Your Location",
        placeholder=my_location or "Enter city name and press Enter",
        key="my_location",
        on_change=create_location_callback
    )

    ##############

    st.header("🎯 Filters")

    st.text_input("Keywords", profile_data.get("keywords", "software engineer"), key="keywords", on_change=save_current_filters)
    st.text_input("Location", profile_data.get("location", "California"), key="location", on_change=save_current_filters)

    countries_dict = get_countries()
    default_country = profile_data.get("country", "United States")
    st.selectbox("Country", list(countries_dict.keys()), index=list(countries_dict.keys()).index(default_country), key="country_name", on_change=save_current_filters)

    languages_dict = get_languages()
    default_language = profile_data.get("language", "English")
    st.selectbox("Language", list(languages_dict.keys()), index=list(languages_dict.keys()).index(default_language), key="language_name", on_change=save_current_filters)

    st.selectbox("Date Posted", ["all", "today", "3days", "week", "month"], index=["all", "today", "3days", "week", "month"].index(profile_data.get("date_posted", "all")), key="date_posted", on_change=save_current_filters)

    st.checkbox("Remote Only", value=profile_data.get("work_from_home", False), key="work_from_home", on_change=save_current_filters)

    st.multiselect("Employment Types", list(employment_type_options.keys()), default=profile_data.get("employment_types", []), key="employment_types", on_change=save_current_filters)

    st.multiselect("Experience", list(experience_options.keys()), default=profile_data.get("job_requirements", []), key="job_requirements", on_change=save_current_filters)

    st.text_input("Company Names (comma-separated)", profile_data.get("company_input", ""), key="company_input", on_change=save_current_filters)

    st.slider(
        "Expected Salary Range (Annual USD)",
        min_value=10000,
        max_value=500000,
        value=tuple(profile_data.get("salary_range", (80000, 180000))),
        step=5000,
        key="salary_range",
        on_change=save_current_filters
    )

    location_set = bool(profile_data.get("my_location"))

    st.slider(
        "Maximum Distance from Location (miles)",
        min_value=5,
        max_value=100,
        value=profile_data.get("distance_radius", 30),
        step=5,
        key="distance_radius",
        on_change=save_current_filters,
        disabled=not location_set
    )

    ##############

    my_latitude = profile_data.get("latitude")
    my_longitude = profile_data.get("longitude")
    radius_miles = st.session_state.get("distance_radius", None)

    if my_latitude is not None and my_longitude is not None and radius_miles:

        if "show_map" not in st.session_state:
            st.session_state["show_map"] = False

        if st.button("🗺️ Show My Location on Map"):
            st.session_state["show_map"] = True

        if st.session_state["show_map"]:

            with st.expander("📍 My Location Map", expanded=True):

                radius_meters = radius_miles * 1609.34
                zoom = 14 - math.log2(radius_meters / 500) + 0.7
                zoom = max(min(zoom, 20), 1)

                # Red area (search radius)
                area_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=[{"position": [my_longitude, my_latitude]}],
                    get_position="position",
                    get_radius=radius_meters,
                    get_fill_color=[255, 0, 0, 60],
                    get_line_color=[255, 0, 0],
                    pickable=False,
                )

                # Green marker for exact location
                center_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=[{"position": [my_longitude, my_latitude]}],
                    get_position="position",
                    get_radius=500,
                    get_fill_color=[0, 255, 0, 200],
                    get_line_color=[0, 128, 0],
                    pickable=False,
                )

                view_state = pdk.ViewState(
                    latitude=my_latitude,
                    longitude=my_longitude,
                    zoom=zoom,
                )

                st.pydeck_chart(pdk.Deck(
                    map_style=config.map_style_jobs,
                    initial_view_state=view_state,
                    layers=[area_layer, center_layer],  # order matters!
                ))

    ##############

    st.slider("Max Jobs", 10, 300, profile_data.get("max_jobs", 100), key="max_jobs", on_change=save_current_filters)

    ##############

    st.header("📄 Resume Upload")

    profile = load_profile(active_profile_name)

    if profile and profile["resume_filename"]:

        st.success(f"📎 Resume attached: {profile['resume_filename']}")

        if st.button("❌ Remove Resume", key="remove_resume"):

            # Clear resume data in profile
            clear_resume(active_profile_name)

            # Refresh to show upload prompt again
            st.rerun()

    else:

        uploaded_file = st.file_uploader("Upload your resume", key="resume_upload")

        if uploaded_file:

            resume_filename = uploaded_file.name
            resume_bytes = uploaded_file.read()

            save_profile(active_profile_name, resume_filename=resume_filename, resume_binary=resume_bytes)
            summarize_resume()

            # Refresh to show attached resume
            st.rerun()

    ##############

    st.divider()

    if st.button("Enrich Jobs", key="enrich_jobs"):
        status, output = summarize_and_embed()
        if not status:
            st.warning(output)

    st.header(f"🤖 Ask the Assistant ({config.llm_model_chat})")

    user_prompt = st.text_area(
        "Enter your question or prompt below:",
        height=150,
        key="llm_user_prompt"
    )

    if st.button("💬 Ask LLM", key="ask_llm_btn"):
        user_prompt = user_prompt.strip()
        if user_prompt:
            process_llm(user_prompt)
        else:
            st.warning("Please enter a prompt before submitting.")

    ##############

    st.divider()

    if st.button("🗑️ Clear Job Cache", use_container_width=False):

        try:
            redis_client.flushdb()
            st.success("✅ Redis job cache cleared.")
        except Exception as e:
            st.error(f"❌ Failed to clear Redis cache: {e}")

    if st.button("🗑️ Clear All Summarizations", use_container_width=False):

        db_session = Session()

        try:
            db_session.query(Job).filter(Job.is_summarized == True).update(
                {Job.is_summarized: False}, synchronize_session=False)
            db_session.commit()
            st.success(f"✅ Cleared summarization.")
        except Exception as e:
            db_session.rollback()
            st.error(f"❌ Failed to clear summarizations: {e}")

    if st.button("🗑️ Clear All Embeddings", use_container_width=False):

        db_session = Session()

        try:
            db_session.query(Job).filter(Job.is_embedded == True).update(
                {Job.is_embedded: False}, synchronize_session=False)
            db_session.execute(delete(JobEmbedding))
            db_session.commit()
            st.success(f"✅ Cleared embeddings.")
        except Exception as e:
            db_session.rollback()
            st.error(f"❌ Failed to clear embeddings: {e}")


def profile_change_callback():

    selected = st.session_state["selected_profile"]
    set_active_profile(selected)

    st.session_state["visible_job_ids"] = None
    st.session_state["visible_job_ids_fav"] = None


def create_profile_callback():

    name = st.session_state.get("profile_name", "").strip()
    if not name:
        return

    all_profiles = get_all_profiles()
    if name in all_profiles:
        st.warning("Profile already exists.")
        return

    if not is_valid_profile_name(name):
        st.error("Invalid name. Use only letters, numbers, _ or - (max 50 chars).")
        return

    save_profile(name, filter_data=get_current_filters())
    set_active_profile(name)

    # clear the input box
    st.session_state["profile_name"] = ""


def is_valid_profile_name(name):
    return re.match(r'^[a-zA-Z0-9_-]{1,50}$', name) is not None


def create_location_callback():

    my_location = st.session_state.get("my_location", "").strip()
    active_profile_name = get_active_profile()

    if not my_location or not active_profile_name:
        return

    status, output = get_coordinates(my_location)
    if not status:
        st.error(f"Failed to set location. {output}")
        return

    latitude = output[0]
    longitude = output[1]

    save_profile(active_profile_name, my_location=my_location, latitude=latitude, longitude=longitude)

    alert = st.success(f"📍 Location set: {my_location} ({latitude}, {longitude})")
    time.sleep(3)
    alert.empty()


def save_current_filters():

    active_profile_name = get_active_profile()
    if active_profile_name:
        save_profile(active_profile_name, filter_data=get_current_filters())


def get_current_filters():

    return {
        "keywords": st.session_state.get("keywords", "software engineer"),
        "location": st.session_state.get("location", "California"),
        "country": st.session_state.get("country_name", "United States"),
        "language": st.session_state.get("language_name", "English"),
        "date_posted": st.session_state.get("date_posted", "all"),
        "work_from_home": st.session_state.get("work_from_home", False),
        "employment_types": st.session_state.get("employment_types", []),
        "job_requirements": st.session_state.get("job_requirements", []),
        "company_input": st.session_state.get("company_input", ""),
        "salary_range": [
            st.session_state.get("salary_range", [80000, 180000])[0],
            st.session_state.get("salary_range", [80000, 180000])[1]
        ],
        "distance_radius": st.session_state.get("distance_radius", 50),
        "max_jobs": st.session_state.get("max_jobs", 100)
    }


def process_llm(user_prompt):

    visible_job_ids_fav = st.session_state.get("visible_job_ids_fav")
    visible_job_ids = st.session_state.get("visible_job_ids")
    visible_job_ids_final = visible_job_ids_fav or visible_job_ids

    if not visible_job_ids_final:
        st.warning("No job listings are currently visible to reference.")
        return

    status, output = summarize_and_embed(visible_job_ids_final)
    if not status:
        st.warning(output)
        return

    status, output = send_prompt_to_llm(user_prompt, visible_job_ids_final)
    if not status:
        st.warning(output)
        return

    st.session_state["llm_response"] = output
