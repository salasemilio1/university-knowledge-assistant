"""
Gemini API client — the only file that knows how to talk to the LLM.

All other modules call `generate()` and receive a plain string back.
This keeps provider-specific logic isolated so swapping to another LLM
later means editing only this file.
"""

import os
import sys
import logging
from pathlib import Path

from dotenv import load_dotenv
from google import genai

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

# Walk up from this file to the project root to find .env
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Model Tiers ───────────────────────────────────────────────────────────────
# Two tiers now that the pipeline is 2 calls instead of 3:
#
#   Call 1 — Router + Complexity Classifier
#     Uses a fast, cheap model. Its only job is structured JSON output
#     (department slugs + simple/complex flag), so quality is secondary.
#
#   Call 2 — Answerer (Synthesis)
#     Uses a larger model that reads the skills_index (and optionally all
#     .txt files) and writes a cited, student-facing answer.
#
# Both can be overridden via environment variables in .env without code changes.

MODEL_ROUTER   = os.getenv("MODEL_ROUTER",   "gemini-3.1-flash-lite-preview")
MODEL_ANSWERER = os.getenv("MODEL_ANSWERER", "gemini-3.1-flash-lite-preview")

# Default fallback if no model is specified
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", MODEL_ANSWERER)


if not GEMINI_API_KEY:
    print(
        "\n✖  GEMINI_API_KEY is not set.\n"
        "   Add it to your .env file at the project root:\n"
        f"   {_PROJECT_ROOT / '.env'}\n"
    )
    sys.exit(1)

# ── Client setup ──────────────────────────────────────────────────────────────

_client = genai.Client(api_key=GEMINI_API_KEY)


# ── Public API ────────────────────────────────────────────────────────────────

def generate(prompt: str, model: str | None = None) -> str:
    """Send a prompt to Gemini and return the response text.

    Args:
        prompt: The full prompt string to send.
        model:  Model name override. Defaults to DEFAULT_MODEL.

    Returns:
        The model's text response, or a fallback error string if the call fails.
    """
    model_name = model or DEFAULT_MODEL
    import time
    
    max_retries = 5
    retry_delay = 5 # seconds

    for attempt in range(max_retries):
        try:
            response = _client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as exc:
            if ("503" in str(exc) or "429" in str(exc)) and attempt < max_retries - 1:
                log.warning("Gemini API error %s (attempt %d/%d). Retrying in %ds...", exc, attempt + 1, max_retries, retry_delay)
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            
            log.error("Gemini API call failed (model=%s): %s", model_name, exc)
            return f"[ERROR] LLM call failed: {exc}"
    
    return "[ERROR] LLM call failed after retries."


def generate_stream(prompt: str, model: str | None = None):
    """Send a prompt to Gemini and yield response text chunks as they arrive.

    Args:
        prompt: The full prompt string to send.
        model:  Model name override. Defaults to DEFAULT_MODEL.

    Yields:
        Text chunks as they are produced by the model.
    """
    model_name = model or DEFAULT_MODEL
    try:
        for chunk in _client.models.generate_content_stream(
            model=model_name,
            contents=prompt,
        ):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        log.error("Gemini streaming failed (model=%s): %s", model_name, exc)
        yield f"\n\n[ERROR] Streaming failed: {exc}"


def extract_json(text: str) -> str:
    """Extract JSON from an LLM response, stripping markdown code blocks.

    Args:
        text: The raw text response from the LLM.

    Returns:
        The clean JSON string ready for json.loads().
    """
    text = text.strip()
    
    # Strip opening markdown block
    if text.startswith("```json"):
        text = text[len("```json"):]
    elif text.startswith("```"):
        text = text[len("```"):]
        
    # Strip closing markdown block
    if text.endswith("```"):
        text = text[:-len("```")]
        
    return text.strip()
