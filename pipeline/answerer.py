"""
Answerer — Call 3 of 3.

Loads the selected .txt documents, concatenates them with source headers,
and asks Gemini to generate a cited answer. Conversation history (last 3
Q&A pairs) is injected here — and only here — to give the model
conversational context.
"""

import logging
from pathlib import Path

from pipeline.gemini_client import generate, MODEL_ANSWERER
from pipeline.prompts import answerer_prompt

log = logging.getLogger(__name__)


# ── Document loading ──────────────────────────────────────────────────────────

def load_documents(doc_list: list[dict]) -> str:
    """Read and concatenate the selected .txt files with source headers.

    Args:
        doc_list: A list of dicts from the retriever, each containing
                  'filename' and 'path' keys.

    Returns:
        A single string with all document contents, each preceded by a
        header like '--- Source: Courses.txt ---'.
    """
    parts = []

    for doc in doc_list:
        path = Path(doc["path"])

        if not path.exists():
            log.warning("Document not found, skipping: %s", path)
            continue

        try:
            text = path.read_text(encoding="utf-8")
            parts.append(
                f"--- Source: {doc['filename']} ---\n\n{text}"
            )
        except Exception as exc:
            log.warning("Failed to read %s: %s", path, exc)
            continue

    if not parts:
        return "[No documents could be loaded.]"

    return "\n\n".join(parts)


# ── History formatting ────────────────────────────────────────────────────────

def format_history(history: list[dict]) -> str | None:
    """Format conversation history as a plaintext block for the prompt.

    Args:
        history: A list of dicts with 'question' and 'answer' keys,
                 oldest first.

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

def answer(question: str, doc_list: list[dict], history: list[dict]) -> str:
    """Generate a cited answer to the student's question.

    Args:
        question: The student's question.
        doc_list: Documents selected by the retriever.
        history:  The last N Q&A pairs for conversational context.

    Returns:
        The model's answer string with inline source citations.
    """
    context = load_documents(doc_list)
    history_block = format_history(history)

    prompt = answerer_prompt(question, context, history_block)
    response = generate(prompt, model=MODEL_ANSWERER)

    # TODO: Add response quality checks here (e.g. verify citations exist)
    return response
