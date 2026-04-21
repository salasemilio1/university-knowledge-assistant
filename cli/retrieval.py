import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline.router import route
from pipeline.answerer import answer

import os
from dotenv import load_dotenv
from google import genai
from google.genai.types import HttpOptions
from google.oauth2 import service_account
from pipeline.gemini_client import create_vertex_client

# ── Configuration ─────────────────────────────────────────────────────────────

load_dotenv()

# All paths are relative to the project root (parent of cli/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_PATH = str(_PROJECT_ROOT / "knowledge_base")
LOG_DIR = _PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "queries.jsonl"

MAX_HISTORY = 3

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── Logging ───────────────────────────────────────────────────────────────────

def _log_query(
    question: str,
    routed_majors: list[str],
    complexity: str,
    answer_text: str,
    duration_seconds: float,
) -> None:
    """Append a structured JSON log entry for one query cycle.

    Args:
        question:         The student's question.
        routed_majors:    Major slugs from the router.
        complexity:       Complexity flag from the router.
        answer_text:      The generated answer.
        duration_seconds: Wall-clock time for the full pipeline.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "routed_majors": routed_majors,
        "selected_docs": [f"{complexity} context"],
        "answer": answer_text,
        "duration_seconds": round(duration_seconds, 2),
    }

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        # Logging failures must never crash the application
        logging.getLogger(__name__).warning("Failed to write log: %s", exc)


# ── History display ───────────────────────────────────────────────────────────

def _print_history(history: list[dict]) -> None:
    """Print the conversation history in a readable format.

    Args:
        history: List of Q&A dicts, oldest first.
    """
    if not history:
        print("\n  No conversation history yet.\n")
        return

    print(f"\n  ── Last {len(history)} Q&A pair(s) ──\n")
    for i, entry in enumerate(history, start=1):
        print(f"  Q{i}: {entry['question']}")
        print(f"  A{i}: {entry['answer'][:200]}{'...' if len(entry['answer']) > 200 else ''}")
        print()


# ── Main loop ─────────────────────────────────────────────────────────────────

def retrieve_response(query: str = None) -> str:
    """Run the interactive advising CLI."""
    print(
        "\n"
        "  ╔══════════════════════════════════════════════════╗\n"
        "  ║  Southwestern University Advising Assistant      ║\n"
        "  ║                                                  ║\n"
        "  ║  Ask any question about courses, degrees,        ║\n"
        "  ║  faculty, clubs, or resources at Southwestern.   ║\n"
        "  ║                                                  ║\n"
        "  ║  Type 'exit' to quit or 'history' to review      ║\n"
        "  ║  recent questions.                               ║\n"
        "  ╚══════════════════════════════════════════════════╝\n"
    )

    history: list[dict] = []
    
    # Mock google_id for CLI usage
    MOCK_GOOGLE_ID = "cli-user"

    llm_client = create_vertex_client()

    while True:
        user_input = query
        if not user_input: # if query passed in via frontend, will be set. otherwise, running as CLI
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n  Goodbye! Good luck with your studies. 👋\n")
                break

            if not user_input:
                continue

        # ── Special commands ──────────────────────────────────────────────────
        if user_input.lower() in ("exit", "quit"):
            print("\n  Goodbye! 👋\n")
            break

        if user_input.lower() == "history":
            _print_history(history)
            continue

        # ── Run the two-call pipeline ───────────────────────────────────────
        start_time = time.time()

        # Phase 1 — Route and Classify
        print("\n  [1/2] Routing and classifying query...")
        try:
            route_result = route(user_input, KNOWLEDGE_BASE_PATH, MOCK_GOOGLE_ID, llm_client=llm_client)
            major_names = ", ".join(route_result.departments)
            print(f"        → Routed to: {major_names} (Complexity: {route_result.complexity})")
        except Exception as exc:
            print(f"\n  ✖ Routing failed: {exc}\n")
            if query: return f"Error: {exc}"
            continue

        # Phase 2 — Generate answer
        print("  [2/2] Generating answer...\n")
        try:
            answer_text = answer(
                question=user_input,
                departments=route_result.departments,
                complexity=route_result.complexity,
                base_path=KNOWLEDGE_BASE_PATH,
                history=history,
                google_id=MOCK_GOOGLE_ID,
                llm_client=llm_client
            )
        except Exception as exc:
            print(f"\n  ✖ Answer generation failed: {exc}\n")
            if query: return f"Error: {exc}"
            continue

        # ── Display the answer ────────────────────────────────────────────────
        print(f"  {answer_text}\n")

        # ── Update conversation memory ────────────────────────────────────────
        history.append({"question": user_input, "answer": answer_text})
        if len(history) > MAX_HISTORY:
            history.pop(0)

        # ── Log the query ─────────────────────────────────────────────────────
        duration = time.time() - start_time
        _log_query(
            question=user_input,
            routed_majors=route_result.departments,
            complexity=route_result.complexity,
            answer_text=answer_text,
            duration_seconds=duration,
        )

        if query:
            return answer_text

if __name__ == "__main__":
    retrieve_response()