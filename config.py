import os

# --- Configs from pipeline/config.py ---
SKILLS_INDEX_FILENAME = "skills_index.md"
ROUTER_TIMEOUT_S = 5
ANSWERER_TIMEOUT_S = 10
FALLBACK_TIMEOUT_S = 8
MAX_RETRIES = 3
RETRY_DELAY = 3
ROUTER_MAX_OUTPUT_TOKENS = 64
ANSWERER_MAX_OUTPUT_TOKENS = 1536
CANNED_FALLBACK_HTML = (
    "<div class='response-block response-error'>"
    "<p>I'm having trouble reaching my knowledge base right now. "
    "Please try again in a moment — I'll be back shortly.</p>"
    "</div>"
)
REGISTRY_FILENAME = "context_registry.json"
DEFAULT_FALLBACK_DEPARTMENTS = ["general"]

# --- Configs from pipeline/gemini_client.py ---
MODEL_ROUTER = os.getenv("MODEL_ROUTER", "gemini-3.1-flash-lite-preview")
MODEL_ANSWERER = os.getenv("MODEL_ANSWERER", "gemini-3-flash-preview")
MODEL_ANSWERER_FALLBACK = os.getenv("MODEL_ANSWERER_FALLBACK", "gemini-2.5-flash")
DEFAULT_MODEL = MODEL_ANSWERER
