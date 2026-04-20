"""
sync_registry.py — Keep context_registry.json in sync with the knowledge base.

This script scans knowledge_base/ for valid context folders (those containing
docs/extracted/), generates a description and keywords for each via Gemini,
and writes a fully merged context_registry.json. It performs an atomic write
so a mid-run crash can never corrupt the live registry.

Usage:
    uv run python scripts/sync_registry.py               # sync new/missing contexts
    uv run python scripts/sync_registry.py --force       # regenerate ALL descriptions
    uv run python scripts/sync_registry.py --dry-run     # preview changes, no writes
    uv run python scripts/sync_registry.py --context math --force
    uv run python scripts/sync_registry.py --knowledge-base /path/to/kb/

If a context shows "missing_from_disk: true" in the registry:
    The folder was registered but has since been deleted from disk. Review
    whether the context should be permanently removed, then delete its entry
    from context_registry.json manually, or re-ingest the source documents.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# ── Bootstrap path so pipeline.* is importable when run as a script ───────────
# Scripts live one level below the project root. We add the root to sys.path
# so `from pipeline.gemini_client import ...` works without installing the pkg.
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from pipeline.gemini_client import generate, extract_json, MODEL_ROUTER
except ImportError as exc:
    print(
        f"\n✖  Cannot import pipeline.gemini_client: {exc}\n"
        f"   Make sure you are running from the project root:\n"
        f"   uv run python scripts/sync_registry.py\n",
        file=sys.stderr,
    )
    raise SystemExit(1)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)
log = logging.getLogger(__name__)

# ── Named constants ───────────────────────────────────────────────────────────

# The registry file consumed by pipeline/router.py
REGISTRY_FILENAME = "context_registry.json"
DEPARTMENTS_FILENAME = "departments.json"

# Valid context folders must contain this subdirectory
EXTRACTED_DOCS_SUBDIR = Path("docs") / "extracted"

# The rich structured index produced by the ingest pipeline.
# Sections 1 (metadata) and 3 (degree path summaries) are the densest input
# for description generation and are cheap to extract by line prefix.
SKILLS_INDEX_FILENAME = "skills_index.md"

# When reading raw .txt files (no skills_index.md), cap total chars sent to
# Gemini to stay within safe token budgets without needing tiktoken.
TXT_CHARS_PER_FILE = 3_000
TXT_TOTAL_CHAR_CAP = 12_000

# Keyword count target — enough for broad query coverage without noise
MAX_KEYWORDS = 15

# Registry fields that must be preserved as-is from an existing entry.
# These are set manually or by the ingest pipeline and carry meaning outside
# this script's scope.
PRESERVED_FIELDS = {"slug", "display_name", "folder", "missing_from_disk"}

# ── Prompt ────────────────────────────────────────────────────────────────────

def _description_prompt(slug: str, content: str) -> str:
    """Build the Gemini prompt for generating description and keywords.

    Args:
        slug:    The context slug (e.g., 'computer_science').
        content: The extracted text content to base the description on.

    Returns:
        A prompt string that instructs the model to return raw JSON only.
    """
    return f"""\
You are a metadata generator for a university advising knowledge base.
A student will ask questions, and a router will use your output to decide
whether this context folder is relevant to their query.

Context folder slug: {slug}

Below is content extracted from this context's knowledge base documents.
Use it to generate a 2-3 sentence plain-English description and up to
{MAX_KEYWORDS} keywords.

=== CONTENT ===
{content}
=== END CONTENT ===

INSTRUCTIONS:
- Return ONLY a valid JSON object — no markdown fences, no preamble.
- description: 2-3 sentences summarizing what this context covers.
- keywords: up to {MAX_KEYWORDS} strings phrased like student questions
  (e.g. "how many credits to graduate"), not catalog entries.
- degree_types: A JSON array of strings listing the degree types this department offers based on the documents, such as ["B.S.", "B.A.", "Minor"], or ["Minor"] if it only offers a minor.

Return this exact shape:
{{
  "description": "...",
  "keywords": ["...", "..."],
  "degree_types": ["...", "..."]
}}
"""


# ── Context discovery ─────────────────────────────────────────────────────────

def discover_contexts(kb_path: Path) -> dict[str, Path]:
    """Scan knowledge_base/ and return folders that have docs/extracted/.

    A folder without docs/extracted/ is an incomplete or non-context directory
    (e.g., a scratch folder, an in-progress ingest). We skip them so we do not
    register half-baked entries.

    Args:
        kb_path: Absolute path to the knowledge_base/ directory.

    Returns:
        A dict mapping folder name (str) → absolute Path to the context folder.
        The folder name is the raw directory name on disk, not the slug.
    """
    found = {}
    for entry in sorted(kb_path.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            # skip macOS metadata dirs like .DS_Store (it's a file, but guard anyway)
            continue
        extracted_dir = entry / EXTRACTED_DOCS_SUBDIR
        if extracted_dir.exists() and extracted_dir.is_dir():
            found[entry.name] = entry
        else:
            log.debug("Skipping '%s': no %s found", entry.name, EXTRACTED_DOCS_SUBDIR)
    return found


def _folder_to_slug(folder_name: str) -> str:
    """Derive a snake_case slug from a folder name.

    This mirrors how the router looks up entries: the folder name is the
    human-readable label (e.g., 'Computer Science'), the slug is the key
    (e.g., 'computer_science').

    Args:
        folder_name: Raw directory name from the filesystem.

    Returns:
        Lowercase string with spaces/hyphens replaced by underscores.
    """
    return folder_name.lower().replace(" ", "_").replace("-", "_")


# ── Content extraction ────────────────────────────────────────────────────────

def _extract_skills_index_sections(index_path: Path) -> str:
    """Pull Section 1 (metadata) and Section 3 (degree summaries) from skills_index.md.

    These sections are the richest, most structured content. Using them instead
    of the whole 60KB file keeps the prompt focused and saves tokens.

    Args:
        index_path: Path to skills_index.md.

    Returns:
        A string containing both sections, or the first 8,000 chars as fallback.
    """
    text = index_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Collect lines belonging to Section 1 and Section 3 (stop at Section 4+).
    # The index uses "## SECTION N" headings reliably.
    in_target = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Start collecting at Section 1 or Section 3
        if stripped.startswith("## SECTION 1") or stripped.startswith("## SECTION 3"):
            in_target = True
        # Stop collecting when we hit Section 4 or higher
        elif stripped.startswith("## SECTION") and in_target:
            section_num_str = stripped.replace("## SECTION", "").strip().split()[0]
            try:
                if int(section_num_str) >= 4:
                    # We've passed Section 3 — stop collecting to avoid bloat
                    in_target = False
            except ValueError:
                pass  # unexpected header format; keep collecting to be safe
        if in_target:
            collected.append(line)

    result = "\n".join(collected).strip()
    # Fallback: if section parsing yields nothing, use the top of the file
    return result if result else text[:8_000]


def _extract_txt_content(extracted_dir: Path) -> str:
    """Read and concatenate .txt files, capped to stay within token budget.

    Args:
        extracted_dir: Path to docs/extracted/.

    Returns:
        Concatenated text across all .txt files, capped at TXT_TOTAL_CHAR_CAP.
    """
    parts: list[str] = []
    total = 0
    for txt_file in sorted(extracted_dir.glob("*.txt")):
        if total >= TXT_TOTAL_CHAR_CAP:
            break
        try:
            chunk = txt_file.read_text(encoding="utf-8")[:TXT_CHARS_PER_FILE]
            parts.append(f"--- {txt_file.name} ---\n{chunk}")
            total += len(chunk)
        except Exception as exc:
            log.warning("Could not read %s: %s", txt_file, exc)
    return "\n\n".join(parts)


def gather_content(context_dir: Path, slug: str) -> str | None:
    """Determine the best available content source for description generation.

    Priority:
      1. skills_index.md (structured, sections 1 + 3)
      2. .txt files from docs/extracted/ (concatenated, capped)
      3. Nothing → return None and skip this context

    Args:
        context_dir: Root directory of the context folder.
        slug:        Slug string (used in log messages only).

    Returns:
        A content string to pass to the Gemini prompt, or None if no content found.
    """
    index_path = context_dir / SKILLS_INDEX_FILENAME
    if index_path.exists():
        log.debug("[%s] Using skills_index.md for description generation", slug)
        return _extract_skills_index_sections(index_path)

    extracted_dir = context_dir / EXTRACTED_DOCS_SUBDIR
    txt_files = list(extracted_dir.glob("*.txt"))
    if txt_files:
        log.debug("[%s] Using %d .txt files for description generation", slug, len(txt_files))
        return _extract_txt_content(extracted_dir)

    log.warning("[%s] No skills_index.md or .txt files found — skipping", slug)
    return None


# ── Gemini description generation ─────────────────────────────────────────────

def generate_metadata(slug: str, content: str) -> dict | None:
    """Call Gemini to produce description and keywords for one context.

    Args:
        slug:    The context slug (used in the prompt for context).
        content: Text content to base the description on.

    Returns:
        A dict with 'description' and 'keywords' keys, or None on failure.
    """
    prompt = _description_prompt(slug, content)
    raw = generate(prompt, model=MODEL_ROUTER)

    # extract_json handles markdown fences the LLM sometimes adds
    clean = extract_json(raw)

    try:
        data = json.loads(clean)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data)}")
        if "description" not in data or "keywords" not in data or "degree_types" not in data:
            raise ValueError(f"Missing required keys in: {list(data.keys())}")
        
        # Enforce degree_types is a list
        if not isinstance(data.get("degree_types"), list):
            data["degree_types"] = [data.get("degree_types")]
        
        # Enforce the keyword cap — the LLM occasionally ignores it
        data["keywords"] = data["keywords"][:MAX_KEYWORDS]
        return data
    except (json.JSONDecodeError, ValueError) as exc:
        log.error("[%s] Failed to parse Gemini metadata response: %s", slug, exc)
        log.debug("[%s] Raw Gemini response: %s", slug, raw[:400])
        return None


# ── Registry I/O ──────────────────────────────────────────────────────────────

def load_registry(registry_path: Path) -> dict[str, dict]:
    """Load the existing registry as a slug-keyed dict.

    If the file doesn't exist yet, return an empty dict — this script will
    create it from scratch on first run.

    Args:
        registry_path: Absolute path to context_registry.json.

    Returns:
        A dict mapping slug (str) → full entry dict.
    """
    if not registry_path.exists():
        log.info("No existing registry found at %s — will create it", registry_path)
        return {}

    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            # The live schema is a list of objects, each with a 'slug' field.
            # We convert to a dict internally for O(1) lookups.
            return {entry["slug"]: entry for entry in raw}
        # Fallback in case someone switches schemas back to a plain dict
        return raw
    except (json.JSONDecodeError, KeyError) as exc:
        log.error("Failed to parse existing registry: %s", exc)
        raise SystemExit(1)

def load_departments(departments_path: Path) -> dict[str, dict]:
    if not departments_path.exists():
        return {}

    try:
        raw = json.loads(departments_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return {entry["department"]: entry for entry in raw}
        return raw
    except (json.JSONDecodeError, KeyError) as exc:
        log.error("Failed to parse existing departments: %s", exc)
        raise SystemExit(1)


def write_registry_atomic(registry_path: Path, entries: list[dict]) -> None:
    """Write the registry list to disk atomically.

    We write to a .tmp file first, then os.replace() it into place. This
    ensures the live registry is never left in a partial state if the process
    is interrupted mid-write.

    Args:
        registry_path: Absolute destination path for context_registry.json.
        entries:       Ordered list of registry entry dicts.
    """
    tmp_path = registry_path.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, registry_path)
    except Exception as exc:
        # If the tmp file was left behind, try to clean it up
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise exc


# ── Core sync logic ───────────────────────────────────────────────────────────

def sync(
    kb_path: Path,
    registry_path: Path,
    force: bool = False,
    dry_run: bool = False,
    only_slug: str | None = None,
) -> dict:
    """Run the full sync: discover, generate, merge, write.

    Args:
        kb_path:       Path to knowledge_base/.
        registry_path: Path to context_registry.json.
        force:         If True, regenerate description/keywords for all contexts.
        dry_run:       If True, print changes but do not write to disk.
        only_slug:     If set, only process this one slug.

    Returns:
        A summary dict with counts: added, updated, skipped, warnings.
    """
    # ── Step 1: Load what already exists ──────────────────────────────────────
    existing = load_registry(registry_path)
    
    departments_path = registry_path.parent / DEPARTMENTS_FILENAME
    existing_departments = load_departments(departments_path)
    
    on_disk = discover_contexts(kb_path)

    # Convert folder names on disk to slug → folder_name mapping
    disk_slug_to_folder: dict[str, str] = {
        _folder_to_slug(name): name for name in on_disk
    }

    summary = {"added": 0, "updated": 0, "skipped": 0, "warnings": 0}

    # ── Step 2: Check registered contexts that no longer exist on disk ────────
    for slug, entry in existing.items():
        if slug not in disk_slug_to_folder:
            log.warning(
                "Context '%s' is registered but NOT found on disk. "
                "Adding 'missing_from_disk: true' flag. "
                "Delete the entry manually if it is no longer needed.",
                slug,
            )
            # Flag it — do not silently drop
            entry["missing_from_disk"] = True
            summary["warnings"] += 1

    # ── Step 3: Build the merged entries list ─────────────────────────────────
    # Start from the existing registry, then add/update from disk discoveries.
    merged: dict[str, dict] = dict(existing)
    merged_departments: dict[str, dict] = dict(existing_departments)

    for slug, folder_name in disk_slug_to_folder.items():
        # If --context was specified, skip everything else
        if only_slug and slug != only_slug:
            continue

        context_dir = on_disk[folder_name]
        is_new = slug not in existing
        needs_regen = is_new or force

        # Clear the missing_from_disk flag if the folder is back on disk
        if slug in merged and merged[slug].get("missing_from_disk"):
            merged[slug].pop("missing_from_disk", None)

        if not needs_regen:
            # Handle migration if degree_types stuck in merged dictionary
            if "degree_types" in merged[slug]:
                dt = merged[slug].pop("degree_types", [])
                if isinstance(dt, str):
                    dt = [d.strip() for d in dt.split(",")]
                merged_departments[folder_name] = {
                    "department": folder_name,
                    "degree_types": dt
                }
                
            log.info("[%s] Already current — skipping (use --force to regenerate)", slug)
            summary["skipped"] += 1
            continue

        # ── Step 3a: Gather content for this context ───────────────────────
        content = gather_content(context_dir, slug)
        if content is None:
            log.warning("[%s] No usable content found — skipping registration", slug)
            summary["warnings"] += 1
            continue

        # ── Step 3b: Generate description and keywords via Gemini ──────────
        log.info("[%s] Generating metadata via Gemini...", slug)
        if dry_run:
            log.info("[%s] --dry-run: would call Gemini and write metadata", slug)
            if is_new:
                summary["added"] += 1
            else:
                summary["updated"] += 1
            continue

        metadata = generate_metadata(slug, content)
        if metadata is None:
            log.warning("[%s] Gemini metadata generation failed — skipping", slug)
            summary["warnings"] += 1
            continue

        # ── Step 3c: Merge into the registry entry ─────────────────────────
        # Preserve identity and manually-set fields; only replace generated ones.
        if is_new:
            merged[slug] = {
                "slug": slug,
                "display_name": folder_name,  # human-readable label from folder name
                "folder": folder_name,         # router uses this to find the directory
                "description": metadata["description"],
                "keywords": metadata["keywords"],
            }
            log.info("[%s] Added new context", slug)
            summary["added"] += 1
        else:
            # For existing entries, only overwrite the generated fields.
            # This preserves any hand-edited 'display_name', 'folder', etc.
            merged[slug]["description"] = metadata["description"]
            merged[slug]["keywords"] = metadata["keywords"]
            merged[slug].pop("degree_types", None)
            log.info("[%s] Updated description and keywords", slug)
            summary["updated"] += 1
            
        merged_departments[folder_name] = {
            "department": folder_name,
            "degree_types": metadata["degree_types"]
        }

    # ── Step 4: Write the final registry ─────────────────────────────────────
    # Convert back to the list-of-objects schema that router.py expects.
    # Sorted by slug for deterministic diffs.
    final_list = [merged[slug] for slug in sorted(merged)]
    final_dept_list = [merged_departments[dept] for dept in sorted(merged_departments)]

    if dry_run:
        log.info("--dry-run: the following would be written to %s:", registry_path)
        print(json.dumps(final_list, indent=2, ensure_ascii=False))
        log.info("--dry-run: the following would be written to %s:", departments_path)
        print(json.dumps(final_dept_list, indent=2, ensure_ascii=False))
    else:
        write_registry_atomic(registry_path, final_list)
        write_registry_atomic(departments_path, final_dept_list)
        log.info("Registry written to %s (%d entries)", registry_path, len(final_list))
        log.info("Departments written to %s (%d entries)", departments_path, len(final_dept_list))

    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sync_registry",
        description="Sync context_registry.json with the knowledge_base/ directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate descriptions for ALL contexts, not just new/missing ones.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change; do not write anything to disk.",
    )
    parser.add_argument(
        "--context",
        metavar="SLUG",
        help="Sync only this context slug (e.g., computer_science).",
    )
    parser.add_argument(
        "--knowledge-base",
        metavar="PATH",
        default=None,
        help=(
            "Override the default knowledge_base/ path. "
            "Defaults to <project_root>/knowledge_base/."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve paths relative to the project root, not the current working dir
    kb_path = (
        Path(args.knowledge_base).resolve()
        if args.knowledge_base
        else _PROJECT_ROOT / "knowledge_base"
    )
    registry_path = kb_path / REGISTRY_FILENAME

    if not kb_path.exists() or not kb_path.is_dir():
        print(
            f"\n✖  knowledge_base directory not found:\n"
            f"   {kb_path}\n"
            f"   Check the path or use --knowledge-base to override.\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if args.dry_run:
        log.info("⚠  DRY RUN — no files will be written")

    summary = sync(
        kb_path=kb_path,
        registry_path=registry_path,
        force=args.force,
        dry_run=args.dry_run,
        only_slug=args.context,
    )

    # Print a structured summary to stdout for easy CI/log parsing
    print(
        f"\nSync complete.\n"
        f"  Added:    {summary['added']} context(s)\n"
        f"  Updated:  {summary['updated']} context(s)\n"
        f"  Skipped:  {summary['skipped']} context(s) (already current)\n"
        f"  Warnings: {summary['warnings']} (see messages above)\n"
    )


if __name__ == "__main__":
    main()
