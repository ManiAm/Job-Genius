
import streamlit as st

import config
import rag_search_remote
from models_sql import Session
from chat_llm import get_resume_text
from job_embedder import summarize_jobs


prompt_resume = """
You are an expert resume coach and writer.

I'm providing two inputs:

1. My current resume (below)
2. A job description for a role I want to apply to (below)

Your task is to:
- Review my resume and suggest improvements to make it sharper, more results-driven, and aligned with modern hiring standards.
- Identify mismatches or gaps between my resume and the job description.
- Rewrite the resume fully to:
    - Use language, tone, and priorities aligned with the job description
    - Emphasize relevant skills, experiences, and keywords
    - Highlight specific achievements and measurable impact

The final version should be professional, focused, and customized for this role.

---
My Resume:
{MY_RESUME_HERE}

---
Job Description:
{JOB_DESCRIPTION_HERE}
"""


prompt_cover_letter = """
You are a professional cover letter writer.

Using the resume and job description below, write a customized, confident, and persuasive cover letter for this role.

The cover letter should:
- Reflect the key highlights of my resume (without repeating it word-for-word)
- Speak directly to the job's responsibilities and requirements
- Convey personality, enthusiasm, and motivation for the role
- Have a professional but personable tone
- Be no longer than one **A4 page** (typically 4 paragraphs)

Avoid generic filler and focus on why I'm a strong match for this specific position.

---
My Resume:
{MY_RESUME_HERE}

---
Job Description:
{JOB_DESCRIPTION_HERE}
"""


def resume_cover_letter_builder(job):

    resume_text = get_resume_text()
    if not resume_text:
        return False, "No resume found"

    ########

    if not job.job_summary:

        with Session() as db_session:

            status, output = summarize_jobs(db_session, [job])
            if not status:
                return False, output

            job = db_session.query(Job).get(job.id)

    job_summary = job.job_summary

    ########

    with st.status(f"Generating updated resume...", expanded=True) as st_status:

        question = prompt_resume.format(
            MY_RESUME_HERE=resume_text,
            JOB_DESCRIPTION_HERE=job_summary
        )

        status, resume_output = rag_search_remote.llm_chat(
            question,
            config.llm_model_chat,
            session_id=f"resume_{job.job_id}"
        )

        st_status.update(label="Resume generated!", state="complete", expanded=False)

    if not status:
        return False, f"resume generation failed: {resume_output}"

    ########

    with st.status(f"Generating cover letter...", expanded=True) as st_status:

        question = prompt_cover_letter.format(
            MY_RESUME_HERE=resume_text,
            JOB_DESCRIPTION_HERE=job_summary
        )

        status, cover_output = rag_search_remote.llm_chat(
            question,
            config.llm_model_chat,
            session_id=f"cover_letter_{job.job_id}"
        )

        st_status.update(label="Cover letter generated!", state="complete", expanded=False)

    if not status:
        return False, f"cover letter generation failed: {cover_output}"

    ########

    return True, {
        "resume": resume_output,
        "cover_letter": cover_output
    }
