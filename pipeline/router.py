"""
Router — Call 1 of 2.

Reads context_registry.json and asks Gemini three things in a single call:
  1. Which department(s) are relevant to the student's question?
  2. Is the question simple or complex?
  3. Is the question off-topic (not university-advising related)?

Resilience
----------
- One attempt only — no retries. The router uses a fast model (gemini-3.1-flash-lite-preview)
  with a 5-second hard timeout.
- If the router times out, fails, or returns an empty department list, the
  caller falls back to a default department ("general") so the pipeline can
  continue. Router failures are invisible to the user.
- If the question is flagged off_topic, RouteResult.off_topic is True and the
  caller must NOT invoke the answerer — return a friendly canned message instead.
"""

import json
import logging
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.gemini_client import generate, extract_json, MODEL_ROUTER, ROUTER_TIMEOUT_S
from pipeline.prompts import router_prompt
from Backend.user_db import get_formatted_user_info

log = logging.getLogger(__name__)

REGISTRY_FILENAME = "context_registry.json"

# Default department used when routing fails entirely.
# "general" covers broad university policy, financial info, and cross-cutting
# advising questions — a safe fallback for any query we can't classify.
DEFAULT_FALLBACK_DEPARTMENTS = ["general"]

# Valid complexity values returned by the LLM. Anything else defaults to complex
# so we never silently under-fetch context.
_VALID_COMPLEXITY = {"simple", "complex"}


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class RouteResult:
    """The output of the router — what to fetch and how much context to load."""
    departments: list[str]       # validated department slugs from the registry
    complexity:  str             # "simple" or "complex"
    off_topic:   bool = False    # True → skip the answerer; return a canned reply


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

def route(question: str, base_path: str, google_id: str, history: list[dict] | None = None, llm_client=None) -> RouteResult:
    """Route a student's question to the right department(s) and classify complexity.

    Makes a single LLM call with a hard 5-second timeout. On any failure the
    function logs a warning and returns a RouteResult pointing at the default
    fallback department so the pipeline can always produce a response.

    Args:
        question:  The student's question.
        base_path: Path to the knowledge_base directory.
        google_id: The student's Google ID (used to personalise routing).

    Returns:
        A RouteResult with validated department slugs, a complexity string, and
        an off_topic flag. Never raises — router failures default gracefully.
    """
    registry = load_registry(base_path)
    registry_path = Path(base_path) / REGISTRY_FILENAME
    registry_json = registry_path.read_text(encoding="utf-8")

    user_info = get_formatted_user_info(google_id)

    # Format history as plain text: "User: ... \nAssistant: ..."
    history_text = ""
    if history:
        turns = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            turns.append(f"{role}: {msg['content']}")
        history_text = "\n".join(turns)

    prompt = router_prompt(question, registry_json, user_info, history=history_text if history_text else None)

    # ── Single-attempt router call ────────────────────────────────────────────
    try:
        raw_response = generate(
            prompt,
            model=MODEL_ROUTER,
            llm_client=llm_client,
            timeout=ROUTER_TIMEOUT_S,
            thinking_level="MINIMAL",
            is_router=True,
        )
    except (FuturesTimeout, Exception) as exc:
        log.warning(
            "Router call failed (%s) — defaulting to %s",
            exc, DEFAULT_FALLBACK_DEPARTMENTS,
        )
        return RouteResult(
            departments=DEFAULT_FALLBACK_DEPARTMENTS,
            complexity="complex",
        )

    # ── Parse and validate response ───────────────────────────────────────────
    clean_json_str = extract_json(raw_response)
    try:
        parsed = json.loads(clean_json_str)

        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object, got: {type(parsed)}")

        raw_departments = parsed.get("departments", [])
        raw_complexity  = parsed.get("complexity", "complex")
        off_topic       = bool(parsed.get("off_topic", False))

        if not isinstance(raw_departments, list):
            raise ValueError(f"'departments' must be a list, got: {type(raw_departments)}")

    except (json.JSONDecodeError, ValueError) as exc:
        log.warning(
            "Router returned unparseable JSON (%s) — defaulting to %s. Raw: %s",
            exc, DEFAULT_FALLBACK_DEPARTMENTS, raw_response[:200],
        )
        return RouteResult(
            departments=DEFAULT_FALLBACK_DEPARTMENTS,
            complexity="complex",
        )

    # ── Off-topic fast exit ───────────────────────────────────────────────────
    if off_topic:
        log.info("Question flagged as off-topic by router")
        return RouteResult(departments=[], complexity="simple", off_topic=True)

    # ── Validate slugs ────────────────────────────────────────────────────────
    valid_departments = [s for s in raw_departments if s in registry]
    if not valid_departments:
        log.warning(
            "Router returned no valid department slugs (got: %s) — defaulting to %s",
            raw_departments, DEFAULT_FALLBACK_DEPARTMENTS,
        )
        valid_departments = DEFAULT_FALLBACK_DEPARTMENTS

    # ── Normalise complexity ──────────────────────────────────────────────────
    complexity = raw_complexity if raw_complexity in _VALID_COMPLEXITY else "complex"
    if complexity != raw_complexity:
        log.warning(
            "Router returned unrecognised complexity '%s'; defaulting to 'complex'.",
            raw_complexity,
        )

    log.info("Routed to %s (complexity=%s)", valid_departments, complexity)
    return RouteResult(departments=valid_departments, complexity=complexity)
