"""
PDF Text Extractor for University Knowledge Base Ingestion
----------------------------------------------------------
Usage:
    python extract_pdf_text.py <directory_name> [--force]
    python extract_pdf_text.py --all [--force]

Options:
    --force   Re-ingest PDFs even if an extracted .txt already exists.
    --all     Process every major directory in the knowledge base.

Example:
    python extract_pdf_text.py computer_science
    python extract_pdf_text.py --all --force

Expected folder structure:
    /knowledge_base
        /<directory_name>
            /docs
                /raw        ← input PDFs go here
                /extracted  ← extracted .txt files saved here (auto-created)
"""

import os
import sys
import pdfplumber
import re
import logging
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Text cleaning ─────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Light cleaning pass on extracted page text.
    - Collapses 3+ consecutive blank lines to 2
    - Strips trailing whitespace from each line
    - Removes common repeating header/footer noise (page numbers, etc.)
    """
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.splitlines()]

    # Remove lines that are purely a page number (e.g. "42", "- 42 -", "Page 42")
    page_number_pattern = re.compile(
        r"^\s*[-–]?\s*(page\s*)?\d{1,4}\s*[-–]?\s*$", re.IGNORECASE
    )
    lines = [line for line in lines if not page_number_pattern.match(line)]

    # Collapse runs of 3+ blank lines into exactly 2
    cleaned_lines = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned_lines.append(line)
        else:
            blank_count = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


_UNIVERSITY_TAG_RE = re.compile(
    r"[\s•·\-–—]*southwestern\s+university[\s•·\-–—]*",
    re.IGNORECASE,
)


def strip_university_tag(text: str) -> str:
    """Remove '• Southwestern University' tag (and variants) from extracted text."""
    return _UNIVERSITY_TAG_RE.sub("", text).strip()


def clean_pdf_stem(stem: str) -> str:
    """Remove the Southwestern University tag from a PDF filename stem, if present."""
    cleaned = _UNIVERSITY_TAG_RE.sub("", stem).strip(" .-–—")
    return cleaned if cleaned else stem



# ── Core extraction ───────────────────────────────────────────────────────────

def extract_pdf(pdf_path: Path) -> str:
    """
    Extract all text from a PDF file.
    - Uses pdfplumber for text-based pages
    - Falls back to OCR for image-based (scanned) pages
    Returns the full document text with page separators.
    """
    full_text_parts = []
    ocr_page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        log.info(f"  Pages to process: {total_pages}")

        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""

            if page_text.strip():
                full_text_parts.append(f"--- Page {i} of {total_pages} ---\n\n{page_text}")
    raw_text = "\n\n".join(full_text_parts)
    return clean_text(raw_text)


# ── Directory processing ──────────────────────────────────────────────────────

def purge_tagged_txt_files(extracted_dir: Path) -> None:
    """
    Delete any .txt files in *extracted_dir* whose content still contains
    the '• Southwestern University' tag. These are either leftover duplicates
    or files from a previously failed ingestion run.
    """
    if not extracted_dir.exists():
        return

    for txt_path in sorted(extracted_dir.glob("*.txt")):
        try:
            content = txt_path.read_text(encoding="utf-8")
        except Exception as exc:
            log.warning(f"  Could not read {txt_path.name} for tag check: {exc}")
            continue

        if _UNIVERSITY_TAG_RE.search(content):
            txt_path.unlink()
            log.info(f"[PURGE]   {txt_path.name}  →  contained university tag, deleted")


def process_directory(directory_name: str, base_path: str = "knowledge_base", force: bool = False) -> None:
    """
    For a given major directory, extract text from all PDFs in /raw
    and save results to /extracted.
    - Strips the '• Southwestern University' tag from extracted text and filenames.
    - Renames PDFs whose stems contained the tag.
    - Skips already-extracted PDFs unless *force* is True.
    """
    raw_dir       = Path(base_path) / directory_name / "docs" / "raw"
    extracted_dir = Path(base_path) / directory_name / "docs" / "extracted"

    # ── Validate input directory ──────────────────────────────────────────────
    if not raw_dir.exists():
        log.error(
            f"Raw directory not found: {raw_dir}\n"
            f"Expected structure: {base_path}/{directory_name}/docs/raw/"
        )
        sys.exit(1)

    # ── Create extracted directory if it doesn't exist ────────────────────────
    extracted_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Extracted output directory: {extracted_dir}")

    # ── Purge any stale .txt files containing the university tag ─────────────
    purge_tagged_txt_files(extracted_dir)

    # ── Find all PDFs ─────────────────────────────────────────────────────────
    pdf_files = sorted(raw_dir.glob("*.pdf"))

    if not pdf_files:
        log.warning(f"No PDF files found in {raw_dir}")
        return

    log.info(f"Found {len(pdf_files)} PDF(s) in {raw_dir}\n")

    # ── Process each PDF ──────────────────────────────────────────────────────
    skipped  = []
    success  = []
    failures = []

    for pdf_path in pdf_files:
        # ── Rename PDF if its stem contains the university tag ─────────────────
        clean_stem = clean_pdf_stem(pdf_path.stem)
        if clean_stem != pdf_path.stem:
            new_pdf_path = pdf_path.with_name(clean_stem + pdf_path.suffix)
            pdf_path.rename(new_pdf_path)
            log.info(f"[RENAME]  {pdf_path.name}  →  {new_pdf_path.name}")
            pdf_path = new_pdf_path

        output_filename = clean_stem + ".txt"
        output_path     = extracted_dir / output_filename

        # Skip if already extracted (unless --force)
        if output_path.exists():
            if not force:
                log.info(f"[SKIP]    {pdf_path.name}  →  already extracted")
                skipped.append(pdf_path.name)
                continue
            output_path.unlink()
            log.info(f"[DELETE]  {output_path.name}  →  removed for re-ingestion")

        log.info(f"[EXTRACT] {pdf_path.name}")

        try:
            extracted_text = extract_pdf(pdf_path)
            extracted_text = strip_university_tag(extracted_text)

            if not extracted_text.strip():
                log.warning(
                    f"  Warning: extraction produced no text for {pdf_path.name}. "
                    "The PDF may be fully image-based and OCR unavailable."
                )

            # Write output
            output_path.write_text(extracted_text, encoding="utf-8")
            file_size_kb = output_path.stat().st_size / 1024
            log.info(f"  Saved → {output_path}  ({file_size_kb:.1f} KB)\n")
            success.append(pdf_path.name)

        except Exception as exc:
            log.error(f"  FAILED to extract {pdf_path.name}: {exc}\n")
            failures.append((pdf_path.name, str(exc)))

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"  Extracted successfully : {len(success)}")
    print(f"  Skipped (already done) : {len(skipped)}")
    print(f"  Failed                 : {len(failures)}")

    if failures:
        print("\nFailed files:")
        for name, reason in failures:
            print(f"  • {name}: {reason}")

    print("=" * 60)


# ── Full knowledge-base scan ──────────────────────────────────────────────────

def scan_all_majors(base_path: str = "knowledge_base", force: bool = False) -> None:
    """
    Iterate over every major directory in *base_path* and run
    process_directory() on each one that contains a docs/raw sub-folder.
    """
    kb_root = Path(base_path)
    if not kb_root.exists():
        log.error(f"Knowledge base root not found: {kb_root.resolve()}")
        sys.exit(1)

    majors = sorted(
        d for d in kb_root.iterdir()
        if d.is_dir() and (d / "docs" / "raw").exists()
    )

    if not majors:
        log.warning(f"No major directories with docs/raw found in {kb_root.resolve()}")
        return

    log.info(f"Scanning {len(majors)} major(s) in {kb_root.resolve()}\n")
    for major in majors:
        log.info(f"{'=' * 60}")
        log.info(f"Processing major: {major.name}")
        log.info(f"{'=' * 60}")
        process_directory(major.name, base_path, force=force)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract text from PDFs in the university knowledge base."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Major directory name inside the knowledge base (omit when using --all).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_majors",
        help="Process every major directory in the knowledge base.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest PDFs even if an extracted .txt file already exists.",
    )
    parser.add_argument(
        "--base",
        default="knowledge_base",
        metavar="PATH",
        help="Path to the knowledge base root (default: knowledge_base).",
    )
    args = parser.parse_args()

    if not args.all_majors and not args.directory:
        parser.print_help()
        sys.exit(1)

    log.info(f"Knowledge base root: {Path(args.base).resolve()}")
    if args.force:
        log.info("Force mode enabled – re-ingesting all PDFs.\n")

    if args.all_majors:
        scan_all_majors(args.base, force=args.force)
    else:
        log.info(f"Starting extraction for: {args.directory}\n")
        process_directory(args.directory, args.base, force=args.force)
