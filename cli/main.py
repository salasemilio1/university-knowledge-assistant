"""
CLI entry point — wires the three-call pipeline into an interactive loop.

No business logic lives here. This file handles:
  1. User input / output
  2. Orchestrating router → retriever → answerer
  3. Conversation memory (last 3 Q&A pairs)
  4. Logging each query cycle to logs/queries.jsonl
"""

from retrieval import retrieve_response

def main() -> None:
    retrieve_response(None)

if __name__ == "__main__":
    main()
