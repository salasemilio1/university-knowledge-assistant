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
from pipeline.prompts import answerer_prompt
from pipeline.router import load_registry
from Backend.user_db import get_formatted_user_info

log = logging.getLogger(__name__)

SKILLS_INDEX_FILENAME = "skills_index.md"
EXTRACTED_DOCS_DIR    = "docs/extracted"


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


def _load_all_txt_files(department_slug: str, base_path: str) -> list[tuple[str, str]]:
    """Read all .txt source files from a department's docs/extracted/ directory.

    Used for complex questions that need the full document set.

    Returns:
        A list of (filename, content) tuples, one per discovered .txt file.
    """
    registry    = load_registry(base_path)
    folder      = registry.get(department_slug, {}).get("folder")

    if not folder:
        return []

    extracted_dir = Path(base_path) / folder / EXTRACTED_DOCS_DIR

    if not extracted_dir.exists():
        log.warning("Extracted docs directory not found: %s", extracted_dir)
        return []

    files = []
    for txt_path in sorted(extracted_dir.glob("*.txt")):
        try:
            files.append((txt_path.name, txt_path.read_text(encoding="utf-8")))
        except Exception as exc:
            log.warning("Failed to read %s: %s", txt_path, exc)

    return files


def load_context(departments: list[str], complexity: str, base_path: str) -> str:
    """Assemble the context string to pass to the answerer prompt.

    Combines context from all routed departments. Each source block is
    labelled so the model can cite its sources in the response.

    Args:
        departments: Validated department slugs from the router.
        complexity:  "simple" → skills_index only; "complex" → index + all txts.
        base_path:   Path to the knowledge_base directory.

    Returns:
        A single string with all relevant content, ready for the prompt.
    """
    parts = []

    for slug in departments:
        # Always include the skills index — it is the backbone of every response
        index_text = _load_skills_index(slug, base_path)
        if index_text:
            parts.append(f"--- Source: {slug}/skills_index.md ---\n\n{index_text}")
        else:
            log.warning("Skipping skills index for '%s' — file not found", slug)

        # For complex questions, also include the full source documents
        if complexity == "complex":
            for filename, content in _load_all_txt_files(slug, base_path):
                parts.append(f"--- Source: {slug}/{filename} ---\n\n{content}")

    if not parts:
        return "[No context could be loaded for this question.]"

    return "\n\n".join(parts)


# ── History formatting ────────────────────────────────────────────────────────

def format_history(history: list[dict]) -> str | None:
    """Format conversation history as a plaintext block for the prompt.

    Args:
        history: A list of dicts with 'question' and 'answer' keys, oldest first.

    Returns:
        A formatted string, or None if history is empty.
    """
    if not history:
        return None

    lines = []
    for i, entry in enumerate(history, start=1):
        lines.append(f"Q{i}: {entry['question']}")
        lines.append(f"A{i}: {entry['answer']}")
        lines.append("")  # blank line between pairs

    return "\n".join(lines).strip()


# ── Core answering ────────────────────────────────────────────────────────────

def answer(
    question:    str,
    departments: list[str],
    complexity:  str,
    base_path:   str,
    history:     list[dict],
    google_id:   str,
    llm_client=None
) -> str:
    """Generate a cited answer to the student's question.

    Args:
        question:    The student's question.
        departments: Department slugs from the router.
        complexity:  "simple" or "complex" — determines how much context to load.
        base_path:   Path to the knowledge_base directory.
        history:     The last N Q&A pairs for conversational context.
        google_id:   The student's Google ID (for profile personalisation).

    Returns:
        The model's answer string with inline source citations.
    """
    context       = load_context(departments, complexity, base_path)
    history_block = format_history(history)
    user_info     = get_formatted_user_info(google_id)

    prompt   = answerer_prompt(question, context, history_block)
    response = generate(prompt, model=MODEL_ANSWERER, llm_client=llm_client)

    # TODO: Add response quality checks here (e.g. verify citations exist)
    return response


def stream_answer(
    question:    str,
    departments: list[str],
    complexity:  str,
    base_path:   str,
    history:     list[dict],
    google_id:   str,
    llm_client=None
):
    """Yield answer chunks for the student's question (streaming variant of answer).

    Signature mirrors answer() exactly — the only difference is that this
    function yields text chunks as they arrive from the model rather than
    returning a single completed string.

    Args:
        question:    The student's question.
        departments: Department slugs from the router.
        complexity:  "simple" or "complex" — determines how much context to load.
        base_path:   Path to the knowledge_base directory.
        history:     The last N Q&A pairs for conversational context.
        google_id:   The student's Google ID (for profile personalisation).

    Yields:
        Raw text chunks as they are produced by the model.
    """
    context       = load_context(departments, complexity, base_path)
    history_block = format_history(history)

    prompt = answerer_prompt(question, context, history_block)
    yield from generate_stream(prompt, model=MODEL_ANSWERER, llm_client=llm_client)
