"""
Gemini / Vertex client wrapper.

All other modules call generate() / generate_stream() and receive plain text
back. This file owns provider-specific auth, model invocation, timeouts, and
fallback logic so callers stay clean.

Resilience model
----------------
Router calls:
  - One attempt only — no retries.
  - 5-second hard timeout. If the router hangs, fail fast and let the caller
    fall back to a default department. Never double the worst-case latency
    by retrying a timed-out router.

Answerer calls:
  - Up to MAX_RETRIES attempts on the primary model (gemini-3-flash-preview)
    on transient 503/429 errors, bounded by ANSWERER_TIMEOUT_S.
  - If the primary times out or exhausts retries, one attempt on the fallback
    model (gemini-2.5-flash), bounded by FALLBACK_TIMEOUT_S.
  - If the fallback also fails, return CANNED_FALLBACK_HTML — a user-facing
    HTML message. A user must always get a response; never surface a
    developer-facing error sentinel.
"""

import json
import logging
import os
import time
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import HttpOptions
from google.oauth2 import service_account

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as config

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# --- Configs ---
# Constants are now imported from the root config.py
ROUTER_TIMEOUT_S = config.ROUTER_TIMEOUT_S
ANSWERER_TIMEOUT_S = config.ANSWERER_TIMEOUT_S
FALLBACK_TIMEOUT_S = config.FALLBACK_TIMEOUT_S
MAX_RETRIES = config.MAX_RETRIES
RETRY_DELAY = config.RETRY_DELAY
ROUTER_MAX_OUTPUT_TOKENS = config.ROUTER_MAX_OUTPUT_TOKENS
ANSWERER_MAX_OUTPUT_TOKENS = config.ANSWERER_MAX_OUTPUT_TOKENS
CANNED_FALLBACK_HTML = config.CANNED_FALLBACK_HTML

MODEL_ROUTER = config.MODEL_ROUTER
MODEL_ANSWERER = config.MODEL_ANSWERER
MODEL_ANSWERER_FALLBACK = config.MODEL_ANSWERER_FALLBACK
DEFAULT_MODEL = config.DEFAULT_MODEL


# ── Client factory ────────────────────────────────────────────────────────────


def create_vertex_client():
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    credentials = None
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

# Shared executor for timeout-bounded API calls.
# One thread per in-flight request is sufficient at this scale.
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="gemini")


# ── Low-level call helpers ────────────────────────────────────────────────────


def _build_config(
    model: str,
    thinking_level: str,
    max_output_tokens: int,
) -> types.GenerateContentConfig:
    """Build a GenerateContentConfig with model-specific thinking config.

    Gemini 3.x models use semantic 'thinking_level' levels.
    Gemini 2.x models use numeric 'thinking_budget' token counts.
    """
    if "gemini-3" in model:
        # Gemini 3.x uses semantic levels (MINIMAL, LOW, MEDIUM, HIGH)
        thinking_config = types.ThinkingConfig(thinking_level=thinking_level)
    else:
        # Gemini 2.x uses numeric token budgets
        budget = {"MINIMAL": 0, "LOW": 512}.get(thinking_level.upper(), 0)
        thinking_config = types.ThinkingConfig(thinking_budget=budget)

    return types.GenerateContentConfig(
        thinking_config=thinking_config,
        max_output_tokens=max_output_tokens,
    )


def _call_api(
    client,
    model: str,
    prompt: str,
    config: types.GenerateContentConfig,
    timeout: float,
) -> str:
    """Make a single blocking API call, bounded by *timeout* seconds.

    Args:
        client:  Initialized Vertex genai Client.
        model:   Model name string.
        prompt:  User prompt text.
        config:  GenerateContentConfig (thinking, max tokens, etc.).
        timeout: Hard wall-clock timeout in seconds.

    Returns:
        The stripped response text.

    Raises:
        FuturesTimeout: If the call exceeds *timeout* seconds.
        Exception:      Any Vertex / network error from the SDK.
    """
    future = _executor.submit(
        client.models.generate_content,
        model=model,
        contents=prompt,
        config=config,
    )
    response = future.result(timeout=timeout)
    return response.text.strip()


# ── Public API ────────────────────────────────────────────────────────────────


def generate(
    prompt: str,
    model: str | None = None,
    llm_client=None,
    timeout: float | None = None,
    thinking_level: str = "LOW",
    max_output_tokens: int | None = None,
    is_router: bool = False,
) -> str:
    """Send a prompt and return the response text.

    For router calls (``is_router=True``) this function makes exactly ONE
    attempt with a 5-second timeout and no retries — callers must handle the
    failure themselves (typically by defaulting to a fallback department).

    For answerer calls this function:
      1. Retries the primary model up to MAX_RETRIES times on 503/429.
      2. Falls back to MODEL_ANSWERER_FALLBACK if the primary times out or
         exhausts its retries.
      3. Returns CANNED_FALLBACK_HTML if the fallback also fails — ensuring
         a user always receives a response.

    Args:
        prompt:            The prompt text to send.
        model:             Override the default model name.
        llm_client:        Override the module-level client (e.g. for tests).
        timeout:           Hard timeout in seconds. Defaults per is_router flag.
        thinking_level:    "MINIMAL" or "LOW" — maps to a token budget.
        max_output_tokens: Token ceiling override.
        is_router:         True → apply router call policy (single attempt, no fallback).

    Returns:
        Response text, or CANNED_FALLBACK_HTML on total failure.
    """
    client = llm_client or _client

    if is_router:
        # ── Router path: one shot, fast fail ─────────────────────────────────
        effective_model = model or MODEL_ROUTER
        effective_timeout = timeout or ROUTER_TIMEOUT_S
        effective_tokens = max_output_tokens or ROUTER_MAX_OUTPUT_TOKENS
        config = _build_config(
            effective_model, thinking_level or "MINIMAL", effective_tokens
        )

        try:
            return _call_api(client, effective_model, prompt, config, effective_timeout)
        except FuturesTimeout:
            log.warning(
                "Router timed out after %ss (model=%s)",
                effective_timeout,
                effective_model,
            )
            raise
        except Exception as exc:
            log.error("Router call failed (model=%s): %s", effective_model, exc)
            raise

    # ── Answerer path: retries + fallback ─────────────────────────────────────
    primary_model = model or MODEL_ANSWERER
    effective_timeout = timeout or ANSWERER_TIMEOUT_S
    effective_tokens = max_output_tokens or ANSWERER_MAX_OUTPUT_TOKENS
    config = _build_config(primary_model, thinking_level or "LOW", effective_tokens)

    retry_delay = RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            return _call_api(client, primary_model, prompt, config, effective_timeout)
        except FuturesTimeout:
            log.warning(
                "Answerer primary timed out after %ss on attempt %d/%d (model=%s) — trying fallback",
                effective_timeout,
                attempt + 1,
                MAX_RETRIES,
                primary_model,
            )
            break  # timeout → don't retry; go straight to fallback
        except Exception as exc:
            is_transient = "503" in str(exc) or "429" in str(exc)
            if is_transient and attempt < MAX_RETRIES - 1:
                log.warning(
                    "Vertex API error %s (attempt %d/%d). Retrying in %ds…",
                    exc,
                    attempt + 1,
                    MAX_RETRIES,
                    retry_delay,
                )
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            log.error("Answerer primary failed (model=%s): %s", primary_model, exc)
            break

    # ── Fallback attempt ──────────────────────────────────────────────────────
    fallback_model = MODEL_ANSWERER_FALLBACK
    fallback_config = _build_config(fallback_model, "LOW", effective_tokens)
    log.info("Attempting fallback model: %s", fallback_model)
    try:
        return _call_api(
            client, fallback_model, prompt, fallback_config, FALLBACK_TIMEOUT_S
        )
    except FuturesTimeout:
        log.error(
            "Fallback model timed out after %ss (model=%s)",
            FALLBACK_TIMEOUT_S,
            fallback_model,
        )
    except Exception as exc:
        log.error("Fallback model call failed (model=%s): %s", fallback_model, exc)

    # ── Last resort ───────────────────────────────────────────────────────────
    log.error(
        "Both primary and fallback answerer calls failed — returning canned response"
    )
    return CANNED_FALLBACK_HTML


def generate_stream(prompt: str, model: str | None = None, llm_client=None):
    """Send a prompt to Gemini and yield response text chunks as they arrive.

    Tokens are yielded immediately on receipt so the client's perceived latency
    reflects time-to-first-token, not time-to-complete-response.

    No fallback is applied to streaming — if the stream breaks mid-response an
    inline error notice is appended rather than starting over (which would
    cause the already-streamed text to confusingly disappear).
    """
    effective_model = model or MODEL_ANSWERER
    client = llm_client or _client
    config = _build_config(effective_model, "LOW", ANSWERER_MAX_OUTPUT_TOKENS)

    try:
        for chunk in client.models.generate_content_stream(
            model=effective_model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        log.error("Vertex streaming failed (model=%s): %s", effective_model, exc)
        yield f"\n\n[I ran into a problem generating that response. Please try again.]"


def extract_json(text: str) -> str:
    """Strip markdown code fences from an LLM JSON response."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json") :]
    elif text.startswith("```"):
        text = text[len("```") :]
    if text.endswith("```"):
        text = text[: -len("```")]
    return text.strip()
