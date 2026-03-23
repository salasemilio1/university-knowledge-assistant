"""
Retriever — Call 2 of 3.

For each routed major, reads the skills_index.md and asks Gemini which
.txt documents should be loaded to answer the question. Includes a fuzzy
filename matcher so the LLM doesn't need to nail the exact casing or
underscore-vs-space convention.
"""

import json
import logging
import re
from pathlib import Path

from pipeline.gemini_client import generate, extract_json, MODEL_RETRIEVER
from pipeline.prompts import retriever_prompt
from pipeline.router import load_registry

log = logging.getLogger(__name__)

# ── Named constants ───────────────────────────────────────────────────────────

SKILLS_INDEX_FILENAME = "skills_index.md"
EXTRACTED_DOCS_DIR = "docs/extracted"


# ── Fuzzy filename matching ───────────────────────────────────────────────────

def _normalize_filename(name: str) -> str:
    """Collapse a filename to a canonical lowercase form for fuzzy matching.

    Strips extension, lowercases, and replaces all non-alphanumeric chars
    with a single underscore. This lets us match 'Clubs and Honor Societies.txt'
    against 'Clubs_and_Honor_Societies.txt' or 'clubs-and-honor-societies.txt'.

    Args:
        name: A filename string (with or without extension).

    Returns:
        A normalized key string, e.g. 'clubs_and_honor_societies'.
    """
    stem = Path(name).stem.lower()
    return re.sub(r"[^a-z0-9]+", "_", stem).strip("_")


def _build_filename_map(extracted_dir: Path) -> dict[str, Path]:
    """Build a mapping from normalized filename → actual file path.

    Args:
        extracted_dir: Path to the docs/extracted directory.

    Returns:
        A dict like {'clubs_and_honor_societies': Path('...Clubs and Honor Societies.txt')}.
    """
    mapping = {}
    if not extracted_dir.exists():
        return mapping

    for filepath in extracted_dir.iterdir():
        if filepath.is_file() and filepath.suffix == ".txt":
            key = _normalize_filename(filepath.name)
            mapping[key] = filepath

    return mapping


def resolve_filename(llm_filename: str, filename_map: dict[str, Path]) -> Path | None:
    """Match an LLM-returned filename against actual files on disk.

    Tries exact match first, then falls back to normalized key matching.

    Args:
        llm_filename:  The filename string the LLM returned.
        filename_map:  The output of _build_filename_map().

    Returns:
        The resolved Path, or None if no match is found.
    """
    # Try exact path match first (in case LLM nails the real name)
    for path in filename_map.values():
        if path.name == llm_filename:
            return path

    # Fall back to normalized matching
    normalized = _normalize_filename(llm_filename)
    return filename_map.get(normalized)


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_skills_index(major_slug: str, base_path: str) -> str:
    """Load the skills_index.md file for a given major.

    Args:
        major_slug: The major's slug key, e.g. 'computer_science'.
        base_path:  Path to the knowledge_base directory.

    Returns:
        The full text content of skills_index.md.

    Raises:
        FileNotFoundError: If the skills index file doesn't exist.
    """
    registry = load_registry(base_path)

    if major_slug not in registry:
        raise FileNotFoundError(
            f"Major slug '{major_slug}' not found in registry."
        )

    folder_name = registry[major_slug]["folder"]
    index_path = Path(base_path) / folder_name / SKILLS_INDEX_FILENAME

    if not index_path.exists():
        raise FileNotFoundError(
            f"Skills index not found: {index_path.resolve()}"
        )

    return index_path.read_text(encoding="utf-8")


# ── Core retrieval ────────────────────────────────────────────────────────────

def retrieve(question: str, major_slugs: list[str], base_path: str) -> list[dict]:
    """Select which .txt documents to load for a student's question.

    Makes one Gemini call per major to pick the right documents from that
    major's skills index.

    Args:
        question:     The student's question.
        major_slugs:  List of major slugs from the router.
        base_path:    Path to the knowledge_base directory.

    Returns:
        A list of dicts: [{"major": slug, "filename": str, "path": Path}, ...]
    """
    registry = load_registry(base_path)
    all_docs = []

    for slug in major_slugs:
        # Load the skills index for this major
        try:
            skills_text = load_skills_index(slug, base_path)
        except FileNotFoundError as exc:
            log.warning("Skipping major '%s': %s", slug, exc)
            continue

        # Ask Gemini which docs to load
        prompt = retriever_prompt(question, skills_text)
        raw_response = generate(prompt, model=MODEL_RETRIEVER)
        clean_json_str = extract_json(raw_response)

        # Parse the filename list
        try:
            filenames = json.loads(clean_json_str)
            if not isinstance(filenames, list):
                raise ValueError(f"Expected JSON array, got: {type(filenames)}")
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning(
                "Could not parse retriever response for '%s': %s — "
                "raw response: %s",
                slug, exc, raw_response[:200],
            )
            continue

        # Resolve each filename against actual files on disk
        folder_name = registry[slug]["folder"]
        extracted_dir = Path(base_path) / folder_name / EXTRACTED_DOCS_DIR
        filename_map = _build_filename_map(extracted_dir)

        for fname in filenames:
            resolved = resolve_filename(fname, filename_map)
            if resolved:
                all_docs.append({
                    "major": slug,
                    "filename": resolved.name,
                    "path": resolved,
                })
            else:
                log.warning(
                    "Could not resolve filename '%s' for major '%s'. "
                    "Available files: %s",
                    fname,
                    slug,
                    [p.name for p in filename_map.values()],
                )

    return all_docs
