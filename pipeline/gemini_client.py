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
# We use separate model tiers for each pipeline stage to optimize for cost
# and performance. Utility calls (routing/retrieval) use cheaper models.

# Call 1: Router
# Gemma 3 4b works for this, as we stress test the system, it wouldn't be a bad idea to upgrade to 12b or even 27b
MODEL_ROUTER = os.getenv("MODEL_ROUTER", "gemma-3-12b-it")

# Call 2: Retriever
MODEL_RETRIEVER = os.getenv("MODEL_RETRIEVER", "gemini-3.1-flash-lite-preview")

# Call 3: Answerer (Synthesis)
MODEL_ANSWERER = os.getenv("MODEL_ANSWERER", "gemini-3.1-flash-lite-preview")
# MODEL_ANSWERER = os.getenv("MODEL_ANSWERER", "gemini-3-flash-preview")

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

    try:
        # TODO: Add retry logic here if needed for production (e.g. tenacity)
        response = _client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return response.text.strip()

    except Exception as exc:
        log.error("Gemini API call failed (model=%s): %s", model_name, exc)
        return f"[ERROR] LLM call failed: {exc}"


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
