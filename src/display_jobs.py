
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
import streamlit as st
import pandas as pd
import pydeck as pdk
import phonenumbers
from phonenumbers import PhoneNumberFormat

import config
from models_sql import Session, Job, Profile
from db_profiles import update_favorite_job
from finnhub_api import Finnhub_REST_API_Client

stock_client = Finnhub_REST_API_Client(url="https://finnhub.io/api", api_ver="v1")


def process_results(job_id_list, profile_data):

    db_session = Session()
    job_list = db_session.query(Job).filter(Job.job_id.in_(job_id_list)).all()

    visible_jobs = update_filter_bar(job_list)

    visible_job_ids = [job.job_id for job in visible_jobs if job.job_id]
    st.session_state["visible_job_ids"] = visible_job_ids

    update_job_map(visible_jobs, profile_data)

    st.success(f"Found {len(job_list)} jobs")

    show_jobs(visible_jobs)


def update_filter_bar(job_list):

    # Helper to extract raw value from label
    def extract_raw_value(label):
        return label.rsplit(" (", 1)[0] if " (" in label else label

    # Get current selections from session_state
    selected_company_label = st.session_state.get("filter_company", "All")
    selected_location_label = st.session_state.get("filter_location", "All")
    selected_employment_label = st.session_state.get("filter_employment", "All")

    selected_company = extract_raw_value(selected_company_label)
    selected_location = extract_raw_value(selected_location_label)
    selected_employment = extract_raw_value(selected_employment_label)

    # Step 1: Pre-filter job list based on current selections
    filtered_jobs = [
        job for job in job_list
        if (selected_company == "All" or (job.company and job.company.name == selected_company))
        and (selected_location == "All" or job.city == selected_location)
        and (selected_employment == "All" or (selected_employment in job.employment_type if job.employment_type else False))
    ]

    # Step 2: Recount values in filtered list
    company_counts = Counter(job.company.name for job in filtered_jobs if job.company)
    location_counts = Counter(job.city for job in filtered_jobs if job.city)
    employment_flat = [etype for job in filtered_jobs if job.employment_type for etype in job.employment_type]
    employment_counts = Counter(employment_flat)

    def format_options(counter):
        return ["All"] + sorted([f"{k} ({v})" for k, v in counter.items()])

    # Step 3: Build UI with filtered options
    st.markdown("### 🔍 Refine Results")
    col1, col2, col3 = st.columns(3)

    with col1:
        company_options = format_options(company_counts)
        selected_company_label = st.selectbox(
            "Company", company_options,
            index=company_options.index(selected_company_label) if selected_company_label in company_options else 0,
            key="filter_company"
        )
        selected_company = extract_raw_value(selected_company_label)

    with col2:
        location_options = format_options(location_counts)
        selected_location_label = st.selectbox(
            "Location", location_options,
            index=location_options.index(selected_location_label) if selected_location_label in location_options else 0,
            key="filter_location"
        )
        selected_location = extract_raw_value(selected_location_label)

    with col3:
        employment_options = format_options(employment_counts)
        selected_employment_label = st.selectbox(
            "Employment Type", employment_options,
            index=employment_options.index(selected_employment_label) if selected_employment_label in employment_options else 0,
            key="filter_employment"
        )
        selected_employment = extract_raw_value(selected_employment_label)

    # Step 4: Apply final filters
    final_result_list = [
        job for job in job_list
        if (selected_company == "All" or (job.company and job.company.name == selected_company))
        and (selected_location == "All" or job.city == selected_location)
        and (selected_employment == "All" or (selected_employment in job.employment_type if job.employment_type else False))
    ]

    final_result_list.sort(key=lambda job: job.title.lower() if job.title else "")

    return final_result_list


def update_job_map(job_list, profile_data):

    data = [
        {
            "lat": job.job_latitude,
            "lon": job.job_longitude
        }
        for job in job_list
        if job.job_latitude is not None and job.job_longitude is not None
    ]

    df = pd.DataFrame(data)

    # Add your current location
    my_latitude = profile_data.get("latitude")
    my_longitude = profile_data.get("longitude")

    if my_latitude and my_longitude:
        user_point = pd.DataFrame([{"lat": my_latitude, "lon": my_longitude}])
        df = pd.concat([df, user_point], ignore_index=True)

    if df.empty:
        st.info("No job locations to display.")
        return

    # Get map bounds
    min_lat, max_lat = df["lat"].min(), df["lat"].max()
    min_lon, max_lon = df["lon"].min(), df["lon"].max()

    # Compute center
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    # Compute zoom level (approximate, tweak padding)
    def compute_zoom(lat_range, lon_range, padding=1.3):
        max_range = max(lat_range, lon_range) * padding
        return 8 - math.log2(max_range + 1e-6)

    zoom = compute_zoom(max_lat - min_lat, max_lon - min_lon, padding=1.3)
    zoom = max(min(zoom, 20), 1)

    # Red circles for jobs
    job_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df[df["lat"] != my_latitude],  # exclude user point
        get_position='[lon, lat]',
        get_fill_color='[255, 0, 0, 255]',
        get_radius=1000,
    )

    # Green circle for your location
    if my_latitude and my_longitude:
        user_layer = pdk.Layer(
            "ScatterplotLayer",
            data=[{"lat": my_latitude, "lon": my_longitude}],
            get_position='[lon, lat]',
            get_fill_color='[0, 255, 0, 255]',
            get_radius=1000,
        )
    else:
        user_layer = None

    # Show map
    layers = [job_layer]
    if user_layer:
        layers.append(user_layer)

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
    )

    st.pydeck_chart(pdk.Deck(
        map_style=config.map_style_location,
        initial_view_state=view_state,
        layers=layers
    ))


def show_jobs(job_list, key_prefix="main"):

    for job in job_list:

        job_id = job.job_id
        job_title = job.title or "N/A"
        company = job.company.name if job.company else "Unknown"

        city = job.city or "N/A"
        country = job.country or "N/A"
        location = f"{city}, {country}" if city != 'N/A' else country

        employment_type = ", ".join(job.employment_type or []) or "N/A"
        salary = job.job_min_salary
        salary_max = job.job_max_salary

        if pd.notnull(salary) and pd.notnull(salary_max):
            estimated_salary = f"{int(salary):,} - {int(salary_max):,}"
        elif pd.notnull(salary):
            estimated_salary = f"{int(salary):,}+"
        else:
            estimated_salary = "N/A"

        posted_at = job.posted_at_utc

        if posted_at:
            try:
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - posted_at).days
                posted = f"{days_ago} days ago"
            except Exception as e:
                posted = "Unknown"
                st.warning(f"Could not parse posted_at: {posted_at} ({e})")
        else:
            posted = "Unknown"

        company_key = f"{key_prefix}_btn_{job_id}"
        show_key = f"{key_prefix}_show_company_info_{job_id}"
        stock_key = f"{key_prefix}_stock_info_{job_id}"

        cols = st.columns([0.93, 0.07])

        with cols[0]:

            label = f"💼 **{job_title}** - {location} - {company} - *Posted {posted}*"

            with st.expander(label, expanded=False):

                logo_url = job.company.logo_url if job.company and job.company.logo_url else None
                if logo_url:
                    st.image(logo_url, width=50)

                st.markdown(f"**🏢 Company:** {company}")

                if st.button(f"🔍 Show More About the Company", key=company_key):
                    st.session_state[show_key] = not st.session_state.get(show_key, False)

                if st.session_state.get(show_key, False):

                    if stock_key not in st.session_state:
                        with st.spinner("Fetching company details..."):
                            st.session_state[stock_key] = get_stock_details(company)

                    stock_info = st.session_state.get(stock_key)

                    if stock_info:

                        st.markdown("#### 🏢 Company Profile")

                        logo_url = stock_info.get("logo", "")
                        if logo_url:
                            st.image(logo_url, width=60)

                        quote = stock_info.get("quote", {})
                        peers = stock_info.get("peers", [])
                        latest_news = stock_info.get("news", [])

                        international = 'N/A'
                        raw_number = stock_info.get('phone')
                        if raw_number:
                            parsed_number = phonenumbers.parse(raw_number, "US")
                            international = phonenumbers.format_number(parsed_number, PhoneNumberFormat.INTERNATIONAL)

                        st.markdown(f"**🏢 Name:** {stock_info.get('name', 'N/A')}")
                        st.markdown(f"**🌍 Country:** {stock_info.get('country', 'N/A')}")
                        st.markdown(f"**🏭 Industry:** {stock_info.get('finnhubIndustry', 'N/A')}")
                        st.markdown(f"**📞 Phone:** {international}")
                        st.markdown(f"**🌐 Website:** {stock_info.get('weburl')}")
                        st.markdown(f"**🏷️ Ticker:** {stock_info.get('ticker', 'N/A')}")
                        st.markdown(f"**💲 Stock Price:** {quote.get('c', 'N/A')}")
                        st.markdown(f"**👥 Peers:** {', '.join(peers) if peers else 'N/A'}")

                        if latest_news:
                            st.markdown("### 📰 Latest News")
                            for article in latest_news:
                                headline = article.get("headline", "No title")
                                url = article.get("url", "#")
                                dt = datetime.utcfromtimestamp(article["datetime"]).strftime("%Y-%m-%d %H:%M UTC")
                                with st.container():
                                    st.markdown(f"**[{headline}]({url})** at *{dt}*")
                    else:
                        st.warning("This company is not publicly traded or financial data is unavailable.")

                st.markdown(f"**📍 Location:** {location}")
                st.markdown(f"**🧾 Employment Type:** {employment_type}")
                st.markdown(f"**💰 Estimated Salary:** {estimated_salary}")
                st.markdown(f"**🕓 Posted:** {posted}")
                st.markdown(f"**🔗 [Job Link]({job.apply_link or '#'})**")

                job_summary = job.job_summary
                if job_summary:
                    st.markdown("#### ✨ Job Highlights")
                    st.markdown(job_summary)
                else:
                    highlights = job.job_highlights
                    if highlights:
                        st.markdown("#### ✨ Job Highlights")
                        for section, bullets in highlights.items():
                            st.markdown(f"**{section}**")
                            for item in bullets:
                                single_line = item.replace("\n", " ").strip()
                                st.markdown(f"- {single_line}")

        with cols[1]:

            profile_name = st.session_state.get("selected_profile", "")

            if "favorite_jobs" not in st.session_state:

                # Sync with DB at first access
                with Session() as db:
                    profile = db.query(Profile).filter(Profile.name == profile_name).first()
                    st.session_state.favorite_jobs = set(profile.favorite_job_ids or [])

            is_fav = job_id in st.session_state.favorite_jobs
            fav_key = f"{key_prefix}_fav_{job_id}_toggle"
            fav_state = st.toggle("🤍", value=is_fav, key=fav_key, help="Mark as favorite")

            if fav_state != is_fav:
                if fav_state:
                    st.session_state.favorite_jobs.add(job_id)
                    update_favorite_job(profile_name, job_id, add=True)
                else:
                    st.session_state.favorite_jobs.discard(job_id)
                    update_favorite_job(profile_name, job_id, add=False)


def get_stock_details(company_name):

    stock_info = {}

    status, output = get_symbol_from_name(company_name)
    if not status:
        print(f"get_symbol_from_name: {output}")
        return stock_info

    company_symbol = output

    status, output = stock_client.company_profile2(company_symbol)
    if status:
        stock_info.update(output)

    status, output = stock_client.company_peers(company_symbol)
    if status:
        stock_info["peers"] = output

    status, output = stock_client.quote(company_symbol)
    if status:
        stock_info["quote"] = output

    to_date = datetime.utcnow().date()
    from_date = to_date - timedelta(days=30)

    # Convert to string format for API
    from_date_str = from_date.strftime("%Y-%m-%d")
    to_date_str = to_date.strftime("%Y-%m-%d")

    status, output = stock_client.company_news(
        company_symbol,
        from_date=from_date_str,
        to_date=to_date_str)

    if status:

        # Sort news by datetime (most recent first)
        sorted_news = sorted(output, key=lambda x: x["datetime"], reverse=True)

        # Get the top 10 most recent news items
        stock_info["news"] = sorted_news[:10]

    return stock_info


def get_symbol_from_name(name):
    """
    Try to resolve a stock symbol from the full or partial company name.
    """

    status, output = stock_client.symbol_lookup(name)
    if status and output:
        return True, output[0]["symbol"]

    name_parts = name.split()

    if len(name_parts) > 1:

        fallback = name_parts[0]
        status, output = stock_client.symbol_lookup(fallback)
        if status and output:
            return True, output[0]["symbol"]

    return False, f"No symbol found for '{name}'"
