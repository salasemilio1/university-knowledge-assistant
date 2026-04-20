"""
Router — Call 1 of 2.

Reads context_registry.json and asks Gemini two things in a single call:
  1. Which department(s) are relevant to the student's question?
  2. Is the question simple or complex?

The 'complexity' flag is used by the answerer (Call 2) to decide how much
context to load:
  - simple  → skills_index.md only (fast; sufficient for most focused questions)
  - complex → skills_index.md + all source .txt files (thorough; for broad questions)
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pipeline.gemini_client import generate, extract_json, MODEL_ROUTER
from pipeline.prompts import router_prompt
from Backend.user_db import get_formatted_user_info

log = logging.getLogger(__name__)

REGISTRY_FILENAME = "context_registry.json"

# Valid complexity values returned by the LLM. Anything else defaults to complex
# so we never silently under-fetch context.
_VALID_COMPLEXITY = {"simple", "complex"}


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class RouteResult:
    """The output of the router — what to fetch and how much context to load."""
    departments: list[str]  # validated department slugs from the registry
    complexity: str         # "simple" or "complex"


# ── Registry loading ──────────────────────────────────────────────────────────

def load_registry(base_path: str) -> dict:
    """Load the department registry from the knowledge base directory.

    Args:
        base_path: Path to the knowledge_base directory.

    Returns:
        A dict mapping department slugs to their metadata.

    Raises:
        SystemExit: If the registry file is missing or cannot be parsed.
    """
    registry_path = Path(base_path) / REGISTRY_FILENAME

    if not registry_path.exists():
        log.error("Registry not found: %s", registry_path)
        raise SystemExit(
            f"\n✖  Could not find {REGISTRY_FILENAME} at:\n"
            f"   {registry_path.resolve()}\n"
        )

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        # Support both list format and pre-keyed dict format
        if isinstance(data, list):
            return {item["slug"]: item for item in data}
        return data
    except (json.JSONDecodeError, KeyError) as exc:
        log.error("Failed to parse registry file: %s", exc)
        raise SystemExit(1) from exc


# ── Core routing ──────────────────────────────────────────────────────────────

def route(question: str, base_path: str, google_id: str, llm_client=None) -> RouteResult:
    """Route a student's question to the right department(s) and classify complexity.

    Makes a single LLM call that returns both the relevant department slugs
    and a simple/complex flag. This replaces the old two-step router+retriever.

    Args:
        question:  The student's question.
        base_path: Path to the knowledge_base directory.
        google_id: The student's Google ID (used to personalise routing).

    Returns:
        A RouteResult with validated department slugs and a complexity string.

    Raises:
        ValueError: If the LLM response cannot be parsed or contains no valid slugs.
                    Callers should surface this as a user-facing error rather than
                    silently falling back, to avoid expensive unnecessary LLM calls.
    """
    registry = load_registry(base_path)
    registry_path = Path(base_path) / REGISTRY_FILENAME
    registry_json = registry_path.read_text(encoding="utf-8")

    user_info = get_formatted_user_info(google_id)

    prompt = router_prompt(question, registry_json, user_info)
    raw_response = generate(prompt, model=MODEL_ROUTER, llm_client=llm_client)
    clean_json_str = extract_json(raw_response)

    # Parse the router's JSON response: {"departments": [...], "complexity": "..."}
    try:
        parsed = json.loads(clean_json_str)

        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object, got: {type(parsed)}")

        raw_departments = parsed.get("departments", [])
        raw_complexity  = parsed.get("complexity", "complex")

        if not isinstance(raw_departments, list):
            raise ValueError(f"'departments' must be a list, got: {type(raw_departments)}")

    except (json.JSONDecodeError, ValueError) as exc:
        log.error(
            "Router failed to return a valid JSON object: %s — raw response: %s",
            exc, raw_response[:200],
        )
        raise ValueError(
            "I wasn't able to determine which department is relevant to your question. "
            "Please try rephrasing it."
        ) from exc

    # Validate slugs against the registry — discard any the LLM hallucinated
    valid_departments = [s for s in raw_departments if s in registry]
    if not valid_departments:
        log.error(
            "Router returned no valid department slugs (got: %s). "
            "Failing fast to avoid running retrieval against all departments.",
            raw_departments,
        )
        raise ValueError(
            "I wasn't able to determine which department is relevant to your question. "
            "Please try rephrasing it."
        )

    # Normalise complexity — if the LLM returns something unexpected, default to complex
    complexity = raw_complexity if raw_complexity in _VALID_COMPLEXITY else "complex"
    if complexity != raw_complexity:
        log.warning(
            "Router returned unrecognised complexity '%s'; defaulting to 'complex'.",
            raw_complexity,
        )

    log.info(
        "Routed to %s (complexity=%s)", valid_departments, complexity
    )
    return RouteResult(departments=valid_departments, complexity=complexity)
