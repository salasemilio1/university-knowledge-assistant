"""
Answerer — Call 2 of 2.

Loads the right context for the student's question and asks Gemini to
generate a cited answer.

Context is selected based on the complexity flag from the router:
  - simple  → skills_index.md only (fast; the index already contains rich
               summaries and critical_data for most advising questions)
  - complex → skills_index.md + all .txt source files in docs/extracted/
               (thorough; for broad questions that need full document detail)

Both answer() and stream_answer() share the same doc-loading logic.
The only difference is that stream_answer() yields chunks instead of
returning a complete string.
"""

import logging
from pathlib import Path

from pipeline.gemini_client import generate, generate_stream, MODEL_ANSWERER
from pipeline.prompts import answerer_prompt, initial_chat_prompt
from pipeline.router import load_registry
from Backend.user_db import get_formatted_user_info

log = logging.getLogger(__name__)

SKILLS_INDEX_FILENAME = "skills_index.md"


# ── Document loading ──────────────────────────────────────────────────────────

def _load_skills_index(department_slug: str, base_path: str) -> str | None:
    """Read the skills_index.md for a department.

    The skills index is a rich summary document containing critical_data
    blocks, course indices, and degree path summaries. It alone is often
    enough to answer focused advising questions.

    Returns:
        The file contents as a string, or None if the file is not found.
    """
    registry = load_registry(base_path)
    folder   = registry.get(department_slug, {}).get("folder")

    if not folder:
        log.warning("No folder mapping for department slug '%s'", department_slug)
        return None

    index_path = Path(base_path) / folder / SKILLS_INDEX_FILENAME

    if not index_path.exists():
        log.warning("Skills index not found: %s", index_path)
        return None

    return index_path.read_text(encoding="utf-8")


def load_context(departments: list[str], base_path: str) -> str:
    """Assemble the context string to pass to the answerer prompt.
    Always loads only the skills_index.md files for provided departments.
    """
    parts = []
    for slug in departments:
        index_text = _load_skills_index(slug, base_path)
        if index_text:
            parts.append(index_text)
        else:
            log.warning("Skipping skills index for '%s' — file not found", slug)

    if not parts:
        return "[No context could be loaded for this question.]"

    return "\n\n".join(parts)


# ── History formatting ────────────────────────────────────────────────────────

def format_history(history: list[dict]) -> str | None:
    """Format conversation history as a plaintext block for the prompt."""
    if not history:
        return None

    lines = []
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")

    return "\n".join(lines).strip()


# ── Core answering ────────────────────────────────────────────────────────────

def answer(
    question:    str,
    departments: list[str],
    base_path:   str,
    history:     list[dict],
    google_id:   str,
    llm_client=None
) -> str:
    """Generate an answer using ONLY the skills_index.md files."""
    context       = load_context(departments, base_path)
    history_block = format_history(history)
    user_info     = get_formatted_user_info(google_id)
    prompt        = answerer_prompt(question, context, history_block, profile=user_info)
    response = generate(prompt, model=MODEL_ANSWERER, llm_client=llm_client)
    return response


def stream_answer(
    question:    str,
    departments: list[str],
    base_path:   str,
    history:     list[dict],
    google_id:   str,
    llm_client=None
):
    """Streaming variant of answer."""
    context       = load_context(departments, base_path)
    history_block = format_history(history)
    user_info     = get_formatted_user_info(google_id)
    prompt        = answerer_prompt(question, context, history_block, profile=user_info)
    yield from generate_stream(prompt, model=MODEL_ANSWERER, llm_client=llm_client)


def initial_chat_response(google_id: str | None = None, llm_client=None) -> str:
    """
    Tailors a default message to the user each time a conversation starts. 
    """
    user_info = get_formatted_user_info(google_id) if google_id else None
    prompt = initial_chat_prompt(profile=user_info)
    return generate(prompt, model=MODEL_ANSWERER, llm_client=llm_client)


def initial_chat_response_alt() -> str:
    """
    This can be used if we want to avoid calling the LLM each time the default message is provided. 
    """
    return (
        "You can ask me about majors, minors, degree requirements, courses, "
        "graduation planning, professors, academic policies, and campus resources. "
        "If you’ve filled out your profile, I can also give more personalized guidance. "
        "Try asking something like: 'What courses should I take next semester?'"
    )
