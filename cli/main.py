"""
CLI entry point — wires the three-call pipeline into an interactive loop.

No business logic lives here. This file handles:
  1. User input / output
  2. Orchestrating router → retriever → answerer
  3. Conversation memory (last 3 Q&A pairs)
  4. Logging each query cycle to logs/queries.jsonl
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline.router import route
from pipeline.retriever import retrieve
from pipeline.answerer import answer

# ── Configuration ─────────────────────────────────────────────────────────────

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
    selected_docs: list[str],
    answer_text: str,
    duration_seconds: float,
) -> None:
    """Append a structured JSON log entry for one query cycle.

    Args:
        question:         The student's question.
        routed_majors:    Major slugs from the router.
        selected_docs:    Filenames from the retriever.
        answer_text:      The generated answer.
        duration_seconds: Wall-clock time for the full pipeline.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "routed_majors": routed_majors,
        "selected_docs": selected_docs,
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

def retrieve_response(query:str) -> str:
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

    while True:

        if not query:
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

        # ── Run the three-call pipeline ───────────────────────────────────────
        start_time = time.time()

        # Phase 1 — Route to the right department(s)
        print("\n  [1/3] Identifying relevant department...")
        try:
            routed_majors = route(user_input, KNOWLEDGE_BASE_PATH)
            major_names = ", ".join(routed_majors)
            print(f"        → Routed to: {major_names}")
        except Exception as exc:
            print(f"\n  ✖ Routing failed: {exc}\n")
            continue

        # Phase 2 — Select documents
        print("  [2/3] Selecting documents...")
        try:
            doc_list = retrieve(user_input, routed_majors, KNOWLEDGE_BASE_PATH)
            doc_names = ", ".join(d["filename"] for d in doc_list)
            print(f"        → Loading: {doc_names}")
        except Exception as exc:
            print(f"\n  ✖ Document selection failed: {exc}\n")
            continue

        if not doc_list:
            print(
                "\n  I couldn't find any relevant documents for that question."
                "\n  Try rephrasing, or contact your academic advisor.\n"
            )
            continue

        # Phase 3 — Generate answer
        print("  [3/3] Generating answer...\n")
        try:
            answer_text = answer(user_input, doc_list, history)
        except Exception as exc:
            print(f"\n  ✖ Answer generation failed: {exc}\n")
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
            routed_majors=routed_majors,
            selected_docs=[d["filename"] for d in doc_list],
            answer_text=answer_text,
            duration_seconds=duration,
        )

def main() -> None:
    retrieve_response(None)

if __name__ == "__main__":
    main()
