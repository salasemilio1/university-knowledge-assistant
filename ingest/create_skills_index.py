"""
create_skills_index.py — Generate a skills_index.md for a knowledge base folder.

This script reads SKILL_major_ingestion.md (the ingestion prompt template),
loads the .txt files from a specified knowledge_base/<folder>/docs/extracted/
directory, passes everything to Gemini, and writes the resulting skills_index.md
back into the knowledge_base/<folder>/ directory.

Usage:
    uv run python ingest/create_skills_index.py <folder>
    uv run python ingest/create_skills_index.py "Computer Science"
    uv run python ingest/create_skills_index.py Anthropology --force

If skills_index.md already exists, the script will abort unless --force is passed.
The Gemini model used is MODEL_ROUTER (cheap, fast) by default; override with
MODEL_ANSWERER or --model to use a higher-quality model for best results.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# ── Bootstrap sys.path so `pipeline.gemini_client` is importable ──────────────
# This script lives inside /ingest, one level below the project root.
_INGEST_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _INGEST_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from pipeline.gemini_client import generate, DEFAULT_MODEL
except ImportError as exc:
    print(
        f"\n✖  Cannot import pipeline.gemini_client: {exc}\n"
        f"   Run this script from the project root:\n"
        f"   uv run python ingest/create_skills_index.py <folder>\n",
        file=sys.stderr,
    )
    raise SystemExit(1)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

# ── Named constants ────────────────────────────────────────────────────────────

# Paths relative to project root
KNOWLEDGE_BASE_DIR = _PROJECT_ROOT / "knowledge_base"
SKILL_INGESTION_FILE = _INGEST_DIR / "SKILL_major_ingestion.md"
OUTPUT_FILENAME = "skills_index.md"
EXTRACTED_DOCS_SUBDIR = Path("docs") / "extracted"

# The ingestion prompt extracted from SKILL_major_ingestion.md lives inside
# a fenced code block. We identify it by its unique prefix line.
PROMPT_FENCE_OPEN = "```"
PROMPT_FENCE_CLOSE = "```"
PROMPT_START_MARKER = "You are an expert academic document analyst"
PROMPT_END_MARKER = "End of skills_index.md. Do not include any text after Section 9."


# ── Prompt extraction ──────────────────────────────────────────────────────────

def extract_ingestion_prompt(skill_file: Path) -> str:
    """Extract the verbatim Gemini prompt from SKILL_major_ingestion.md.

    The prompt lives inside a triple-backtick block in the .md file. We
    extract only the content between those fences — not the surrounding prose.

    Args:
        skill_file: Path to SKILL_major_ingestion.md.

    Returns:
        The raw prompt string, with placeholder markers still in place.

    Raises:
        SystemExit: If the prompt cannot be located in the file.
    """
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_block = False
    prompt_lines: list[str] = []
    found_start = False

    for line in lines:
        if not in_block and line.strip() == PROMPT_FENCE_OPEN:
            # Peek ahead: is the NEXT non-empty line the start of our prompt?
            # We set a flag so we can collect on the NEXT iteration.
            in_block = True
            prompt_lines = []
            continue

        if in_block:
            # The block ends at the closing fence
            if line.strip() == PROMPT_FENCE_CLOSE and prompt_lines:
                # Check if this block contains the correct prompt
                combined = "\n".join(prompt_lines)
                if PROMPT_START_MARKER in combined:
                    found_start = True
                    break  # This is the block we want — stop collecting
                else:
                    # Not our target block; continue scanning
                    in_block = False
                    prompt_lines = []
                    continue
            prompt_lines.append(line)

    if not found_start:
        print(
            f"\n✖  Could not locate the ingestion prompt in:\n"
            f"   {skill_file}\n"
            f"   Expected a fenced code block starting with:\n"
            f"   '{PROMPT_START_MARKER}'\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return "\n".join(prompt_lines)


# ── Document loading ───────────────────────────────────────────────────────────

def load_extracted_documents(extracted_dir: Path) -> list[tuple[str, str]]:
    """Load all .txt files from a docs/extracted/ directory.

    Args:
        extracted_dir: Path to the extracted docs directory.

    Returns:
        A list of (filename, content) tuples, sorted alphabetically.

    Raises:
        SystemExit: If no .txt files are found.
    """
    txt_files = sorted(extracted_dir.glob("*.txt"))

    if not txt_files:
        print(
            f"\n✖  No .txt files found in:\n"
            f"   {extracted_dir}\n"
            f"   Make sure the folder has been ingested (PDFs extracted to .txt).\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    docs: list[tuple[str, str]] = []
    for path in txt_files:
        try:
            content = path.read_text(encoding="utf-8")
            docs.append((path.name, content))
            log.info("Loaded: %s (%d chars)", path.name, len(content))
        except Exception as exc:
            log.warning("Could not read %s: %s — skipping", path.name, exc)

    return docs


# ── Prompt assembly ────────────────────────────────────────────────────────────

def _build_document_block(docs: list[tuple[str, str]]) -> str:
    """Format the loaded documents into the INPUT DOCUMENTS section of the prompt.

    Args:
        docs: List of (filename, content) tuples.

    Returns:
        A formatted string ready to be injected into the prompt template.
    """
    parts = []
    for filename, content in docs:
        parts.append(
            f"[DOCUMENT]\n"
            f"Filename: {filename}\n"
            f"{content}"
        )
    return "\n\n".join(parts)


def build_prompt(
    raw_prompt_template: str,
    major_name: str,
    docs: list[tuple[str, str]],
    model_name: str,
) -> str:
    """Assemble the final Gemini prompt by substituting placeholders.

    The template from SKILL_major_ingestion.md uses these placeholders:
      [MAJOR_NAME], [DOCUMENT 1] ... [DOCUMENT N], [DATE], [MODEL_NAME]

    We replace the document block wholesale between the sentinel markers,
    and fill in the other fields directly.

    Args:
        raw_prompt_template: The verbatim prompt text from the skill file.
        major_name:          The human-readable major name.
        docs:                Loaded (filename, content) pairs.
        model_name:          The model being used (for metadata embedding).

    Returns:
        The final, fully resolved prompt string.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    doc_block = _build_document_block(docs)

    # Build the formatted document section that replaces the
    # template's document placeholder block
    doc_section = (
        f"--- INPUT DOCUMENTS ---\n\n"
        f"{doc_block}\n\n"
        f"--- END DOCUMENTS ---"
    )

    # Replace placeholders in the template
    prompt = raw_prompt_template
    prompt = prompt.replace("[MAJOR_NAME]", major_name)
    prompt = prompt.replace("[DATE]", today)
    prompt = prompt.replace("[MODEL_NAME]", model_name)
    prompt = prompt.replace("[N]", str(len(docs)))

    # Replace the template's INPUT DOCUMENTS block.
    # The template has a block between "--- INPUT DOCUMENTS ---" and
    # "--- END DOCUMENTS ---" with example placeholders — replace the whole thing.
    doc_start_marker = "--- INPUT DOCUMENTS ---"
    doc_end_marker = "--- END DOCUMENTS ---"
    if doc_start_marker in prompt and doc_end_marker in prompt:
        before = prompt[: prompt.index(doc_start_marker)]
        after = prompt[prompt.index(doc_end_marker) + len(doc_end_marker) :]
        prompt = before + doc_section + after
    else:
        # Fallback: append docs at the end if markers aren't in this version
        log.warning(
            "Could not find document sentinel markers in the prompt template. "
            "Appending documents at the end."
        )
        prompt = prompt + "\n\n" + doc_section

    return prompt


# ── Output writing ─────────────────────────────────────────────────────────────

def write_skills_index(output_path: Path, content: str) -> None:
    """Write the generated skills_index.md to disk.

    Args:
        output_path: Destination file path.
        content:     The generated skills_index content from Gemini.
    """
    output_path.write_text(content, encoding="utf-8")
    log.info("Written: %s (%d chars)", output_path, len(content))


# ── Core orchestration ─────────────────────────────────────────────────────────

def create_skills_index(
    folder_name: str,
    force: bool = False,
    model: str | None = None,
) -> None:
    """Run the full ingestion pipeline for a given knowledge base folder.

    Args:
        folder_name: The directory name inside knowledge_base/ (e.g. "Computer Science").
        force:       If True overwrite an existing skills_index.md.
        model:       Model name override. Defaults to DEFAULT_MODEL.
    """
    # ── Resolve paths ──────────────────────────────────────────────────────────
    context_dir = KNOWLEDGE_BASE_DIR / folder_name
    extracted_dir = context_dir / EXTRACTED_DOCS_SUBDIR
    output_path = context_dir / OUTPUT_FILENAME

    if not context_dir.exists():
        print(
            f"\n✖  Folder not found in knowledge_base/:\n"
            f"   {context_dir}\n"
            f"   Available folders:\n"
            + "".join(
                f"   - {d.name}\n"
                for d in sorted(KNOWLEDGE_BASE_DIR.iterdir())
                if d.is_dir() and not d.name.startswith(".")
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not extracted_dir.exists():
        print(
            f"\n✖  docs/extracted/ not found in:\n"
            f"   {context_dir}\n"
            f"   This folder has not been ingested yet.\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if output_path.exists() and not force:
        print(
            f"\n⚠  skills_index.md already exists for '{folder_name}'.\n"
            f"   Use --force to regenerate it.\n"
            f"   Path: {output_path}\n"
        )
        raise SystemExit(0)

    # ── Step 1: Load the ingestion skill prompt ────────────────────────────────
    log.info("Reading ingestion skill from: %s", SKILL_INGESTION_FILE)
    if not SKILL_INGESTION_FILE.exists():
        print(
            f"\n✖  SKILL_major_ingestion.md not found at:\n"
            f"   {SKILL_INGESTION_FILE}\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    raw_prompt = extract_ingestion_prompt(SKILL_INGESTION_FILE)
    log.info("Prompt template extracted (%d chars)", len(raw_prompt))

    # ── Step 2: Load extracted .txt documents ──────────────────────────────────
    log.info("Loading documents from: %s", extracted_dir)
    docs = load_extracted_documents(extracted_dir)
    log.info("Loaded %d document(s)", len(docs))

    # ── Step 3: Assemble the Gemini prompt ─────────────────────────────────────
    model_name = model or DEFAULT_MODEL
    log.info("Using model: %s", model_name)

    prompt = build_prompt(
        raw_prompt_template=raw_prompt,
        major_name=folder_name,
        docs=docs,
        model_name=model_name,
    )
    log.info("Final prompt assembled (%d chars)", len(prompt))

    # ── Step 4: Call Gemini ────────────────────────────────────────────────────
    print(f"\n  Generating skills_index.md for '{folder_name}' via {model_name}...")
    print(f"  Documents: {[name for name, _ in docs]}")
    print(f"  This may take 30-90 seconds for large knowledge bases.\n")

    response = generate(prompt, model=model_name)

    if response.startswith("[ERROR]"):
        print(
            f"\n✖  Gemini returned an error:\n   {response}\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # ── Step 5: Write output ───────────────────────────────────────────────────
    write_skills_index(output_path, response)

    print(
        f"\n✓  skills_index.md written successfully!\n"
        f"   Path: {output_path}\n"
        f"   Length: {len(response)} chars\n"
        f"\n  ⚠  Please validate the output against the Post-Generation Checklist\n"
        f"     in SKILL_major_ingestion.md before using this index in production.\n"
    )


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_skills_index",
        description=(
            "Generate a skills_index.md for a knowledge_base folder using Gemini. "
            "The folder must contain a docs/extracted/ subdirectory with .txt files."
        ),
    )
    parser.add_argument(
        "folder",
        help=(
            "Name of the folder inside knowledge_base/ to process. "
            "Use the exact directory name, e.g. 'Computer Science' or 'Anthropology'."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing skills_index.md. By default, the script aborts if one exists.",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL_NAME",
        default=None,
        help=(
            "Override the Gemini model. Defaults to the DEFAULT_MODEL in gemini_client.py. "
            "For best quality, consider using a Pro-tier model: e.g. gemini-1.5-pro."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    create_skills_index(
        folder_name=args.folder,
        force=args.force,
        model=args.model,
    )


if __name__ == "__main__":
    main()
