
import time
import streamlit as st
from datetime import datetime, timezone
from nominatim_api import distance_between_coords

from locale_utils import get_countries, get_languages
from sidebar_processor import employment_type_options, experience_options
from models_sql import Session, Job, Company
from db_profiles import load_profile
from JSearch_api import JSearch_REST_API_Client

jSearch = JSearch_REST_API_Client(url="https://jsearch.p.rapidapi.com")


def start_job_search():

    keywords = st.session_state.keywords
    location = st.session_state.location
    country = get_countries()[st.session_state.country_name]
    language = get_languages()[st.session_state.language_name]
    date_posted = st.session_state.date_posted
    work_from_home = st.session_state.work_from_home
    employment_types = ",".join([employment_type_options[label] for label in st.session_state.employment_types]) if st.session_state.employment_types else None
    job_requirements = ",".join([experience_options[label] for label in st.session_state.job_requirements]) if st.session_state.job_requirements else None

    distance_radius = st.session_state.distance_radius

    selected_profile = st.session_state.get("selected_profile", "default")
    profile_data = load_profile(selected_profile)

    my_latitude = profile_data.get("latitude")
    my_longitude = profile_data.get("longitude")

    selected_companies = [c.strip() for c in st.session_state.company_input.split(",") if c.strip()]
    salary_min, salary_max = st.session_state.salary_range

    max_jobs = st.session_state.max_jobs

    page_num = 1
    num_pages = 10
    unique_job_ids = set()
    result_list = []
    try_count = 1
    try_count_max = 1

    status_placeholder = st.empty()

    while True:

        print(f"Query jobs - page_num={page_num}, num_pages={num_pages}")

        status, output = jSearch.job_search(
            keywords=keywords,
            location=location,
            country=country,
            language=language,
            date_posted=date_posted,
            work_from_home=work_from_home,
            employment_types=employment_types,
            job_requirements=job_requirements,
            page_num=page_num,
            num_pages=num_pages,
            timeout=90)

        if status:

            if not output:
                break

            for job in output:

                job_id = job.get("job_id")

                if job_id and job_id not in unique_job_ids:

                    unique_job_ids.add(job_id)

                    if is_candidate(job, distance_radius, my_latitude, my_longitude):
                        result_list.append(job)

            status_placeholder.info(f"🔍 Jobs found so far: {len(result_list)}")

            if len(result_list) >= max_jobs:
                break

            page_num += num_pages
            time.sleep(3)

        else:

            print(f"try ({try_count}/{try_count_max}): {output}.")

            if try_count >= try_count_max:
                print("Maximum retry limit reached.")
                break

            try_count += 1
            time.sleep(3)

    insert_jobs_db(result_list)

    job_ids = [job["job_id"] for job in result_list if "job_id" in job]
    st.session_state["job_id_list"] = job_ids


def is_candidate(job_details, distance_radius, my_latitude, my_longitude):

    job_latitude = job_details.get("job_latitude", None)
    job_longitude = job_details.get("job_longitude", None)

    if not job_latitude or not job_longitude:
        return True

    if not distance_radius:
        return True

    if not my_latitude or not my_longitude:
        return True

    my_loc = (my_latitude, my_longitude)
    job_loc = (job_latitude, job_longitude)

    distance = distance_between_coords(my_loc, job_loc, unit="miles")

    if distance and distance <= distance_radius:
        return True

    # job_title = job_details.get("job_title", None)
    # employer_name = job_details.get("employer_name", None)
    # print(f"Removing {job_title} | {employer_name}. Distance: {distance}")

    return False


def insert_jobs_db(result_list):

    db_session = Session()

    added_at = datetime.now(timezone.utc)

    for job_data in result_list:

        job_id = job_data.get("job_id")
        if not job_id:
            continue

        # Check if job already exists
        existing = db_session.query(Job).filter_by(job_id=job_id).first()
        if existing:
            continue

        # Get or create the company
        company_name = job_data.get("employer_name", "Unknown Company")
        company = db_session.query(Company).filter_by(name=company_name).first()

        if not company:

            company = Company(
                name=company_name,
                logo_url=job_data.get("employer_logo"),
                website=job_data.get("employer_website")
            )

            db_session.add(company)
            db_session.flush()  # Ensure company.id is available for FK

        job = Job(
            job_id=job_id,
            added_at=added_at,
            country=job_data.get("job_country"),
            state=job_data.get("job_state"),
            city=job_data.get("job_city"),
            location=job_data.get("job_location"),
            job_latitude=job_data.get("job_latitude"),
            job_longitude=job_data.get("job_longitude"),
            title=job_data.get("job_title"),
            description=job_data.get("job_description"),
            job_highlights=job_data.get("job_highlights"),
            job_benefits=job_data.get("job_benefits"),
            posted_at_utc=job_data.get("job_posted_at_datetime_utc"),
            posted_at_ts=job_data.get("job_posted_at_timestamp"),
            is_remote=job_data.get("job_is_remote"),
            employment_type=job_data.get("job_employment_types", []),
            job_min_salary=job_data.get("job_min_salary"),
            job_max_salary=job_data.get("job_max_salary"),
            job_salary_period=job_data.get("job_salary_period"),
            publisher=job_data.get("job_publisher"),
            is_direct_apply=job_data.get("job_is_direct_apply"),
            apply_link=job_data.get("job_apply_link"),
            apply_options=job_data.get("job_apply_options"),
            job_google_link=job_data.get("job_google_link"),
            company=company)

        db_session.add(job)

    db_session.commit()
