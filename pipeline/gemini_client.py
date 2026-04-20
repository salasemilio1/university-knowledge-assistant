"""
Gemini / Vertex client wrapper.

All other modules call generate() / generate_stream() and receive plain text
back. This file owns provider-specific auth and model invocation.
"""

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.types import HttpOptions
from google.oauth2 import service_account

log = logging.getLogger(__name__)

# Walk up from this file to the project root to find .env
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

MODEL_ROUTER = os.getenv("MODEL_ROUTER", "gemini-2.5-flash")
MODEL_ANSWERER = os.getenv("MODEL_ANSWERER", "gemini-2.5-flash")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", MODEL_ANSWERER)


def create_vertex_client():
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    credentials = None

    # Local dev path: JSON stored directly in .env
    if "GOOGLE_SERVICE_ACCOUNT_JSON" in os.environ:
        service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    return genai.Client(
        vertexai=True,
        project=project_id,
        location=location,
        credentials=credentials,
        http_options=HttpOptions(api_version="v1"),
    )


_client = create_vertex_client()


def generate(prompt: str, model: str | None = None, llm_client=None) -> str:
    """Send a prompt to Gemini on Vertex and return the response text."""
    model_name = model or DEFAULT_MODEL
    client = llm_client or _client

    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as exc:
            if ("503" in str(exc) or "429" in str(exc)) and attempt < max_retries - 1:
                log.warning(
                    "Vertex API error %s (attempt %d/%d). Retrying in %ds...",
                    exc, attempt + 1, max_retries, retry_delay
                )
                time.sleep(retry_delay)
                retry_delay *= 2
                continue

            log.error("Vertex API call failed (model=%s): %s", model_name, exc)
            return f"[ERROR] LLM call failed: {exc}"

    return "[ERROR] LLM call failed after retries."


def generate_stream(prompt: str, model: str | None = None, llm_client=None):
    """Send a prompt to Gemini on Vertex and yield response text chunks."""
    model_name = model or DEFAULT_MODEL
    client = llm_client or _client

    try:
        for chunk in client.models.generate_content_stream(
            model=model_name,
            contents=prompt,
        ):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        log.error("Vertex streaming failed (model=%s): %s", model_name, exc)
        yield f"\n\n[ERROR] Streaming failed: {exc}"


def extract_json(text: str) -> str:
    """Extract JSON from an LLM response, stripping markdown code blocks."""
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):]
    elif text.startswith("```"):
        text = text[len("```"):]

    if text.endswith("```"):
        text = text[:-len("```")]

    return text.strip()
