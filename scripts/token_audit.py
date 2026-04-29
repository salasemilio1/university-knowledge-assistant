"""
token_audit.py — Audit token counts for each department in the knowledge base.

Usage:
    uv run python scripts/token_audit.py
    uv run python scripts/token_audit.py --departments "Computer Science, Biology"
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# ── Bootstrap path so pipeline.* is importable ──────────────────────────────
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from pipeline.gemini_client import create_vertex_client, DEFAULT_MODEL
except ImportError as exc:
    print(f"\n✖ Cannot import pipeline.gemini_client: {exc}\n", file=sys.stderr)
    raise SystemExit(1)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Suppress HTTP request logs from dependencies
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)

# ── Constants ────────────────────────────────────────────────────────────────
KB_DIR = _PROJECT_ROOT / "knowledge_base"
SKILLS_FILE = "skills_index.md"
EXTRACTED_DIR = Path("docs") / "extracted"

# ── Core Logic ───────────────────────────────────────────────────────────────

def count_tokens(client, text_list: list[str]) -> int:
    """Use Gemini API to count tokens for a list of strings."""
    if not text_list:
        return 0
    try:
        # Filter out empty strings
        clean_list = [t for t in text_list if t.strip()]
        if not clean_list:
            return 0
        
        response = client.models.count_tokens(
            model=DEFAULT_MODEL,
            contents=clean_list,
        )
        return response.total_tokens
    except Exception as exc:
        log.error(f"Error counting tokens: {exc}")
        return 0

def get_department_tokens(client, dept_path: Path):
    """Calculate token counts for a single department."""
    skills_path = dept_path / SKILLS_FILE
    extracted_path = dept_path / EXTRACTED_DIR
    
    skills_text = ""
    if skills_path.exists():
        skills_text = skills_path.read_text(encoding="utf-8")
    
    extracted_texts = []
    if extracted_path.exists() and extracted_path.is_dir():
        for f in sorted(extracted_path.glob("*.txt")):
            try:
                extracted_texts.append(f.read_text(encoding="utf-8"))
            except Exception as exc:
                log.warning(f"Could not read {f.name}: {exc}")
    
    skills_tokens = count_tokens(client, [skills_text]) if skills_text else 0
    extracted_tokens = count_tokens(client, extracted_texts) if extracted_texts else 0
    
    return skills_tokens, extracted_tokens

def main():
    parser = argparse.ArgumentParser(description="Audit token counts for the knowledge base.")
    parser.add_argument(
        "--departments", 
        help="Comma-separated list of departments to audit (e.g. 'Computer Science, Biology')"
    )
    args = parser.parse_args()

    if not KB_DIR.exists():
        log.error(f"Knowledge base directory not found: {KB_DIR}")
        sys.exit(1)

    # Initialize client
    log.info(f"Initializing Gemini client (Model: {DEFAULT_MODEL})...")
    client = create_vertex_client()

    # Discover departments
    all_depts = sorted([d.name for d in KB_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")])
    
    target_depts = all_depts
    if args.departments:
        requested = [d.strip() for d in args.departments.split(",")]
        target_depts = [d for d in all_depts if d in requested]
        # Check for missing requested departments
        missing = [d for d in requested if d not in all_depts]
        for m in missing:
            log.warning(f"⚠️  Department '{m}' not found in knowledge base.")

    if not target_depts:
        log.error("No valid departments selected for audit.")
        sys.exit(1)

    log.info(f"Auditing {len(target_depts)} departments...\n")
    
    # Table Header
    header = f"{'Department':<30} | {'Skills Tokens':>15} | {'Docs Tokens':>15} | {'Total Context':>15}"
    separator = "-" * len(header)
    log.info(header)
    log.info(separator)

    total_skills = 0
    total_docs = 0
    
    for dept_name in target_depts:
        dept_path = KB_DIR / dept_name
        skills_tok, docs_tok = get_department_tokens(client, dept_path)
        
        dept_total = skills_tok + docs_tok
        log.info(f"{dept_name[:30]:<30} | {skills_tok:>15,} | {docs_tok:>15,} | {dept_total:>15,}")
        
        total_skills += skills_tok
        total_docs += docs_tok

    log.info(separator)
    grand_total = total_skills + total_docs
    log.info(f"{'GRAND TOTAL':<30} | {total_skills:>15,} | {total_docs:>15,} | {grand_total:>15,}")
    log.info(f"\nAudit complete. Grand total tokens: {grand_total:,}")

if __name__ == "__main__":
    main()
