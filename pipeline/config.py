"""
Configuration of the response pipeline, separated by file.
"""


# answerer.py

SKILLS_INDEX_FILENAME = "skills_index.md"


# gemini_client.py

# ── Timeout constants (seconds) ───────────────────────────────────────────────

ROUTER_TIMEOUT_S   = 5    # hard limit for the router; fail fast, no retries
ANSWERER_TIMEOUT_S = 10   # primary answerer timeout before attempting fallback
FALLBACK_TIMEOUT_S = 8    # fallback answerer timeout before returning canned response

# ── Retry policy ──────────────────────────────────────────────────────────────
# Retries are applied to the answerer primary only, not the router or fallback.

MAX_RETRIES  = 3
RETRY_DELAY  = 3  # seconds before first retry; doubles on each subsequent attempt

# ── Token ceilings ────────────────────────────────────────────────────────────

ROUTER_MAX_OUTPUT_TOKENS   = 64
ANSWERER_MAX_OUTPUT_TOKENS = 1536

# ── Canned last-resort response ───────────────────────────────────────────────
# Returned when both the primary and fallback answerer calls fail or time out.
# Must always be a user-friendly HTML string — never a developer sentinel.

CANNED_FALLBACK_HTML = (
    "<div class='response-block response-error'>"
    "<p>I'm having trouble reaching my knowledge base right now. "
    "Please try again in a moment — I'll be back shortly.</p>"
    "</div>"
)


# router.py

REGISTRY_FILENAME = "context_registry.json"

# Default department used when routing fails entirely.
# "general" covers broad university policy, financial info, and cross-cutting
# Registry mapping department slugs -> folder names. If the router
# picks a slice that isn't here, it's ignored.
DEFAULT_FALLBACK_DEPARTMENTS = ["general"]