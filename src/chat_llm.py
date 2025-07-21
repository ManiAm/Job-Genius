
import hashlib
import json
import re
import streamlit as st

import config
import rag_search_remote
from models_sql import Session, Profile


instructions = """
You are a professional Job Advisor assisting users in evaluating job opportunities.
You will be given context documents (retrieved job descriptions, highlights, company details, etc.) along with a user's question or preference.
Use only the provided context to guide your response - do not make up details that are not explicitly mentioned.

Your goal is to help the user make an informed career decision. Specifically:
- Understand the user's priorities (e.g., remote work, salary, benefits, skills match, company size).
- Extract and compare relevant information from the job postings.
- Explain trade-offs clearly (e.g., stability vs. growth, salary vs. flexibility).
- Recommend the most suitable job based on the user's stated goals.

Be concise, objective, and user-centric.
If the context is insufficient, tell the user what information is missing.
"""

instructions_resume = """
The user's resume is provided at the end of the context.
Use it to assess how well each job matches the user's background, skills, and experience.
Consider resume-job alignment when scoring or recommending jobs.
"""


def send_prompt_to_llm(user_prompt, job_ids_to_process):

    if not rag_search_remote.is_healthy():
        return False, "RAG-Talk is not reachable"

    ###########

    global instructions
    resume_summary = get_user_resume()
    if resume_summary:
        instructions += instructions_resume + "\n\n" + resume_summary

    ###########

    batch_id = compute_batch_id(job_ids_to_process)

    collection_name = f"jobs_{config.embed_model}_{batch_id}"
    collection_name = re.sub(r"[^a-zA-Z0-9_-]", "_", collection_name)

    with st.status(f"Generating advice...", expanded=True) as st_status:

        st.write(f"Loading embedding model: {config.embed_model}...")

        status, output = rag_search_remote.load_model([config.embed_model])
        if not status:
            return False, f"Cannot load model: {output}"

        st.write(f"Analyzing {len(job_ids_to_process)} job context...")

        status, output = rag_search_remote.rag_chat(
            user_prompt,
            config.llm_model_chat,
            config.embed_model,
            collection_name,
            instructions=instructions,
            session_id=f"job_{batch_id}",
            score_threshold=0.7,
            max_documents=10
        )

        st_status.update(label="Response received!", state="complete", expanded=False)

    if not status:
        return False, output

    return True, output


def get_user_resume():

    profile_name = st.session_state.get("selected_profile", "")
    if not profile_name:
        return None

    with Session() as db_session:
        profile = db_session.query(Profile).filter(Profile.name == profile_name).first()
        if profile and profile.resume_summary:
            return profile.resume_summary

    return None


def compute_batch_id(job_ids_to_process: list[str]) -> str:

    sorted_ids = sorted(job_ids_to_process)
    hash_input = json.dumps(sorted_ids).encode("utf-8")
    return hashlib.sha256(hash_input).hexdigest()[:16]  # 16-char ID
