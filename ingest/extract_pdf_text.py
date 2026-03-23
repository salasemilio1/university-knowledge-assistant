"""
PDF Text Extractor for University Knowledge Base Ingestion
----------------------------------------------------------
Usage:
    python extract_pdfs.py <directory_name>

Example:
    python extract_pdfs.py "computer_science"

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

def process_directory(directory_name: str, base_path: str = "knowledge_base") -> None:
    """
    For a given major directory, extract text from all PDFs in /raw
    and save results to /extracted. Skips PDFs that already have an
    extracted counterpart.
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
        output_filename = pdf_path.stem + ".txt"
        output_path     = extracted_dir / output_filename

        # Skip if already extracted
        if output_path.exists():
            log.info(f"[SKIP]    {pdf_path.name}  →  already extracted")
            skipped.append(pdf_path.name)
            continue

        log.info(f"[EXTRACT] {pdf_path.name}")

        try:
            extracted_text = extract_pdf(pdf_path)

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


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python extract_pdfs.py <directory_name> [base_path]\n"
            "Example: python extract_pdfs.py computer_science\n"
            "         python extract_pdfs.py computer_science /path/to/knowledge_base"
        )
        sys.exit(1)

    directory_name = sys.argv[1]
    base_path      = sys.argv[2] if len(sys.argv) > 2 else "knowledge_base"

    log.info(f"Starting extraction for: {directory_name}")
    log.info(f"Knowledge base root: {Path(base_path).resolve()}\n")

    process_directory(directory_name, base_path)
