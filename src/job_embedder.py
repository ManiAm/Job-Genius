
import hashlib
import json
import re
import streamlit as st

import config
import rag_search_remote
from models_sql import Session, Job, JobEmbedding


summarization_prompt = """
You are a career assistant helping candidates understand job postings.

Given the following job posting text, extract and summarize the following key information:

1. **Role Overview** - What are the primary responsibilities and objectives of the position?
2. **Seniority Level** - Determine whether the role is Entry-Level, Junior, Mid-Level, Senior, or Executive.
3. **Required Skills & Technologies** - List the core skills, tools, or technologies mentioned or implied.
4. **Preferred Experience or Qualifications** - Summarize any additional desirable qualifications.
5. **Company or Role Highlights** - Mention any unique benefits, perks, or noteworthy aspects of the company or role.

Keep the summary concise and structured using bullet points where appropriate.

Here is the job text:

"""

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

def send_prompt_to_llm(user_prompt):

    visible_job_ids = st.session_state.get("visible_job_ids")
    if not visible_job_ids:
        st.warning("No job listings are currently visible to reference.")
        return None

    batch_id = compute_batch_id(visible_job_ids)

    db_session = Session()

    ################

    status, output = summarize_and_embed(db_session, visible_job_ids)
    if not status:
        st.warning(output)
        return None

    status, output = rag_search_remote.get_collections()
    if not status:
        st.warning(f"get_collections error: {output}")
        return None

    existing_collections = output

    ################

    collection_name = f"jobs_{config.embed_model}_{batch_id}"
    collection_name = re.sub(r"[^a-zA-Z0-9_-]", "_", collection_name)

    if collection_name not in existing_collections:

        status, output = store_embedding(
            db_session,
            batch_id,
            collection_name,
            visible_job_ids)

        if not status:
            st.warning(output)
            return None

    ################

    with st.spinner("Analyzing job context and generating advice..."):

        status, output = rag_search_remote.rag_chat(
            user_prompt,
            config.llm_model_chat,
            config.embed_model,
            collection_name,
            instructions=instructions,
            score_threshold=0.7,
            max_documents=10
        )

    if not status:
        st.warning(output)
        return None

    return output


def compute_batch_id(visible_job_ids: list[str]) -> str:

    sorted_ids = sorted(visible_job_ids)
    hash_input = json.dumps(sorted_ids).encode("utf-8")
    return hashlib.sha256(hash_input).hexdigest()[:16]  # 16-char ID


def summarize_and_embed(db_session, visible_job_ids):

    jobs_not_summarized = (
        db_session.query(Job)
        .filter(Job.job_id.in_(visible_job_ids), Job.is_summarized==False)
        .all()
    )

    if jobs_not_summarized:

        status, output = summarized_emails(db_session, jobs_not_summarized)
        if not status:
            return False, output

    ################

    jobs_not_embedded = (
        db_session.query(Job)
        .filter(Job.job_id.in_(visible_job_ids), Job.is_summarized==True, Job.is_embedded==False)
        .all()
    )

    if jobs_not_embedded:

        status, output = embed_emails(db_session, jobs_not_embedded)
        if not status:
            return False, output

    ################

    return True, None


def summarized_emails(db_session, jobs_not_summarized):

    if not rag_search_remote.is_healthy():
        return False, "RAG-Talk is not reachable"

    #############

    status, output = rag_search_remote.get_llm_models()
    if not status:
        return False, output

    existing_models = output

    if config.llm_model_summarization not in existing_models:
        return False, f"LLM model {config.llm_model_summarization} not loaded."

    #############

    status, output = get_max_characters_llm(config.llm_model_summarization)
    if not status:
        return False, f"get_max_characters_llm: {output}"

    context_length_characters = int(output)

    #############

    global summarization_prompt

    with st.status("Start Summarization...", expanded=True) as st_status:

        st.write(f"Summarizing {len(jobs_not_summarized)} jobs with {config.llm_model_summarization}...")

        for job in jobs_not_summarized:

            summarization_prompt_final = summarization_prompt + "\n\n" + extract_job(job)

            if len(summarization_prompt_final) > context_length_characters:

                summarization_prompt_final = summarization_prompt + "\n\n" + extract_job(job, include_highlights=False)

                if len(summarization_prompt_final) > context_length_characters:
                    st.warning(f"job text length exceeds maximum context length {context_length_characters}")

            status, final_summary = rag_search_remote.llm_chat(
                summarization_prompt,
                config.llm_model_summarization,
                session_id="llm_combine_summary")

            if not status:
                return False, final_summary

            job_header_str = extract_job(job, include_body=False)
            job.job_summary = job_header_str + "\n\n" + final_summary
            job.is_summarized = True

            db_session.add(job)
            db_session.commit()

        st_status.update(label="Summarization complete", state="complete", expanded=False)

    return True, None


def get_max_characters_llm(llm_model):

    status, output = rag_search_remote.get_llm_info(llm_model)
    if not status:
        return False, f"cannot get LLM model info: {output}"

    context_len = output.get("llama.context_length", None)
    if not context_len:
        return False, f"cannot get context length of LLM model {llm_model}"

    avg_chars_per_token = 3.5  # in English
    approx_max_characters = int(context_len) * avg_chars_per_token

    return True, int(approx_max_characters)


def extract_job(job, include_header=True, include_body=True, include_highlights=True):

    parts = []

    if include_header:
        parts.extend(extract_job_header(job))

    if include_body:
        parts.extend(extract_job_body(job, include_highlights))

    job_str = "\n".join(part for part in parts if part.strip())

    return job_str


def extract_job_header(job):

    return [
        f"Company: {job.company.name if job.company else 'N/A'}",
        f"Job Location: {job.location or job.city or ''}",
        f"Remote: {'Yes' if job.is_remote else 'No'}",
        f"Employment Type: {', '.join(job.employment_type or [])}",
        f"Job Title: {job.title}"
    ]


def extract_job_body(job, include_highlights=True):

    parts = []

    parts.append(f"Job Description: {job.description or 'N/A'}")

    if include_highlights and job.job_highlights:

        highlights = "\n".join([
            f"{section}: {', '.join(items)}"
            for section, items in job.job_highlights.items()
            if items  # skip empty lists
        ])

        parts.append(f"Job Highlights:\n{highlights}")

    parts.append(f"Job Benefits: {job.job_benefits or 'N/A'}")

    return parts


def embed_emails(db_session, jobs_not_embedded):

    if not rag_search_remote.is_healthy():
        return False, "RAG-Talk is not reachable"

    with st.status("Start Embedding...", expanded=True) as st_status:

        st.write(f"Loading embedding model: {config.embed_model}...")

        status, output = rag_search_remote.load_model([config.embed_model])
        if not status:
            return False, f"Cannot load model: {output}"

        ################

        status, output = get_max_characters_embedding(config.embed_model)
        if not status:
            return False, output

        chunk_size = output

        ################

        st.write(f"Embedding {len(jobs_not_embedded)} jobs...")

        for job in jobs_not_embedded:

            status, output = rag_search_remote.get_embedding(
                job.job_summary,
                config.embed_model,
                chunk_size=chunk_size
            )

            if not status:
                return False, f"Embedding error: {output}"

            vectors = output.get("vectors", [])
            chunk_text = output.get("chunk_text", [])

            if len(vectors) != len(chunk_text):
                st.warning("Mismatch between number of vectors and chunk texts.")
                continue

            for idx, (vector, text) in enumerate(zip(vectors, chunk_text)):

                db_session.add(JobEmbedding(
                    job_id=job.id,
                    chunk_index=idx,
                    chunk_text=text,
                    embedding=vector))

            job.is_embedded = True

            db_session.add(job)
            db_session.commit()

        ################

        st_status.update(label="Embedding done!", state="complete", expanded=False)

    return True, None


def get_max_characters_embedding(embed_model):

    status, output = rag_search_remote.get_max_tokens(embed_model)
    if not status:
        return False, f"cannot get embedding model max tokens: {output}"

    max_tokens = output

    avg_chars_per_token = 3.5  # in English
    approx_max_characters = max_tokens * avg_chars_per_token

    return True, approx_max_characters


def store_embedding(db_session, batch_id, collection_name, visible_job_ids):

    if not rag_search_remote.is_healthy():
        return False, "RAG-Talk is not reachable"

    with st.status("Storing Embeddings...", expanded=True) as st_status:

        st.write(f"Creating collection {collection_name}...")

        status, output = rag_search_remote.create_collection(
            collection_name,
            config.embed_model)

        if not status:
            return False, f"create_collection error: {output}"

        jobs_embedded = (
            db_session.query(Job)
            .filter(Job.job_id.in_(visible_job_ids), Job.is_summarized==True, Job.is_embedded==True)
            .all()
        )

        if len(jobs_embedded) != len(visible_job_ids):
            return False, "Not all visible jobs were embedded!"

        for job in jobs_embedded:

            metadata = {
                "source"   : "Job Genius",
                "batch_id" : batch_id,
                "job_id"   : job.job_id,
                "title"    : job.title,
                "company"  : job.company.name,
            }

            vectors = [e.embedding for e in job.embeddings]
            chunk_texts = [e.chunk_text for e in job.embeddings]

            status, output = rag_search_remote.add_points(
                config.embed_model,
                collection_name,
                vectors,
                texts=chunk_texts,
                metadata=metadata)

            if not status:
                return False, output

        ################

        st_status.update(label="Storing embedding done!", state="complete", expanded=False)

    return True, None
