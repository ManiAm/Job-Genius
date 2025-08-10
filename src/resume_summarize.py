
import re
import mimetypes
import magic
import pytesseract
import html2text
import pdfplumber
import streamlit as st
from docx import Document
from io import BytesIO
from PIL import Image

import config
import rag_search_remote
from models_sql import Session, Profile


summarization_resume_prompt = """
You are an expert career assistant and AI resume analyst.

Your task is to extract structured, high-quality information from a technical resume to support job matching, scoring, and recommendation.

The goal is to understand the candidate's background, expertise, and value proposition. Focus on highlighting work that demonstrates strong technical depth, real-world impact, and alignment with roles in software engineering, systems engineering, embedded systems, or networking.

Given the following resume text, extract and summarize the most relevant and important information into the following structured categories:

1. **Professional Summary**:
   - Write a concise 2-4 sentence paragraph summarizing the candidate's career highlights, strengths, and technical focus areas.

2. **Top Skills and Technologies**:
   - Extract a bullet-point list of programming languages, tools, platforms, protocols, and technologies mentioned or clearly implied.
   - Group or tag them where relevant (e.g., Programming Languages, Databases, DevOps, etc.).

3. **Key Areas of Expertise**:
   - List 4-8 high-level domains or themes such as embedded systems, CI/CD, simulation, automation, network protocols, telemetry, etc.

4. **Work Experience Highlights**:
   For each relevant role:
   - Company
   - Title
   - Duration (start and end dates or years)
   - Bullet points describing the most impactful contributions (focus on scale, innovation, and technologies used)

5. **Education**:
   - Degree
   - Field of study
   - University name
   - Dates attended (or graduation year)

6. **Publications and Research (if applicable)**:
   - List up to 5 notable publications, conference papers, or research contributions.
   - Include titles and venue if available.

7. **Notable Projects or Open Source Contributions**:
   - List named projects with a short description and technologies involved.
   - Prioritize innovation, scale, and real-world utility.

8. **Other Relevant Attributes** (if any):
   - Teaching, leadership, awards, international experience, or lab/testbed work.

Return your response in well-formatted **Markdown** for readability and optionally include a structured **JSON block** for programmatic access if requested.

Resume:
\"\"\"
[Insert resume text here]
\"\"\"
"""


def summarize_resume():

    profile_name = st.session_state.get("selected_profile", "")
    if not profile_name:
        return

    with Session() as db_session:

        profile = db_session.query(Profile).filter(Profile.name == profile_name).first()
        if not profile:
            return

        with st.status("Preparing Resume...", expanded=True) as st_status:

            st.write(f"Extracting text from the resume...")

            status, output = extract_resume_text(db_session, profile)
            if not status:
                st.error(output)
                return

            resume_text = output

            ##########

            global summarization_resume_prompt

            st.write(f"Summarizing resume...")

            summarization_prompt_final = summarization_resume_prompt + "\n\n" + resume_text

            if not rag_search_remote.is_healthy():
                st.error("RAG-Search is not reachable")
                return

            status, output = rag_search_remote.llm_chat(
                summarization_prompt_final,
                config.llm_model_summarization,
                session_id="llm_resume_summary")

            if not status:
                st.error(output)
                return

            profile.resume_summary = output
            db_session.add(profile)
            db_session.commit()

            ##########

            st_status.update(label="Resume preparation complete", state="complete", expanded=False)


def extract_resume_text(db, profile):

    resume_filename = profile.resume_filename
    resume_bytes = profile.resume_binary

    if not resume_filename or not resume_bytes:
        return False, "resume data is not available"

    effective_mime = get_mime_type(resume_filename, resume_bytes)
    resume_text = extract_text(effective_mime, resume_bytes)

    try:
        profile.resume_text = resume_text
        db.commit()
        return True, resume_text
    except Exception as e:
        db.rollback()
        return False, f"Failed to save resume text: {e}"
    finally:
        db.close()


def get_mime_type(filename, binary_data):

    try:
        detected_type = magic.from_buffer(binary_data, mime=True)
        if detected_type:
            return detected_type
    except Exception:
        pass  # Ignore magic failures silently

    # Guess file extension and type
    guessed_type, _ = mimetypes.guess_type(filename)
    if guessed_type:
        return guessed_type

    return "application/octet-stream"


def extract_text(effective_mime, binary_data):

    text_data = ""

    if effective_mime in ["text/plain"]:

        try:
            text_data = binary_data.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"Error: extract_text: {e}")
            pass

    elif effective_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":

        try:
            doc = Document(BytesIO(binary_data))
            text_data = "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"Error: extract_text: {e}")
            pass

    elif effective_mime == "application/pdf":

        try:
            with pdfplumber.open(BytesIO(binary_data)) as pdf:
                all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            text_data = all_text.strip()
        except Exception as e:
            print(f"Error: extract_text: {e}")
            pass

    elif effective_mime == "text/html":

        try:
            html_txt = binary_data.decode('utf-8', errors='ignore')
            status, output = html_to_text(html_txt)
            if status and output:
                text_data = output
        except Exception as e:
            print(f"Error: extract_text: {e}")
            pass

    elif effective_mime in ["image/jpeg", "image/png"]:

        try:
            image = Image.open(BytesIO(binary_data))
            text = pytesseract.image_to_string(image)
            text_data = text.strip()
        except Exception as e:
            print(f"Error: extract_text: {e}")
            pass

    else:

        print(f"Warning: unsupported MIME type: {effective_mime}")

    return text_data.replace('\x00', '')


def html_to_text(html_text):

    try:

        h = html2text.HTML2Text()

        h.ignore_links = True           # Do not include hyperlinks
        h.ignore_images = True          # Skip image tags
        h.body_width = 0                # Do not wrap text
        h.ignore_emphasis = True        # Remove **bold** and _italics_
        h.skip_internal_links = True    # Avoid internal anchors
        h.ignore_tables = True          # Do not include tables
        h.protect_links = True

        text = h.handle(html_text)

        # Remove invisible or formatting Unicode characters
        text = re.sub(r"[\u200c\u200d\u200e\u200f\u202a-\u202e\u2060-\u206f\u00ad\xa0]", " ", text)

        # Replace multiple consecutive spaces or tabs with a single space
        text = re.sub(r"[ \t]+", " ", text)

        # Normalize newlines (remove lines that are empty or have only whitespace)
        text = re.sub(r"\n\s*\n+", "\n\n", text)

        return True, text.strip()

    except Exception as E:

        return False, f"Error in parsing html: {str(E)}"
