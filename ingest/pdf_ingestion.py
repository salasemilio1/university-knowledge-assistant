"""
pdf_ingestion.py
================
Entry point for the PDF ingestion pipeline.

    1. Accept a PDF file path as ``sys.argv[1]``
    2. Call LandingAI agentic-document-analysis API (dpt-2-mini model)
    3. Extract ground-truth text page-by-page with PyMuPDF (fitz)
    4. Reconcile LandingAI chunks against PyMuPDF ground truth
    5. Write the reconciled JSON to ``<pdf_stem>_ingested.json``
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict

import fitz  # pymupdf
import requests

# import environment variables
from dotenv import load_dotenv
load_dotenv()

# Add project root to sys.path so absolute imports like 'ingest.clean_chunks' 
# work when running this file directly as a script.
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from ingest.clean_chunks import reconcile_document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LandingAI API
# ---------------------------------------------------------------------------

_LANDINGAI_URL = "https://api.va.landing.ai/v1/ade/parse"


def call_landingai(pdf_path: str) -> dict:
    """Send the PDF to LandingAI's agentic-document-analysis endpoint
    using the **dpt-2-mini** model and return the parsed JSON response.

    Reads ``LANDINGAI_API_KEY`` from the environment.

    Raises
    ------
    EnvironmentError
        If the API key is not set.
    RuntimeError
        If the API call fails (non-2xx status).
    """
    api_key = os.environ.get("LANDINGAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "LANDINGAI_API_KEY environment variable is not set."
        )

    with open(pdf_path, "rb") as f:
        response = requests.post(
            _LANDINGAI_URL,
            headers={"Authorization": f"Basic {api_key}"},
            files={"document": (Path(pdf_path).name, f, "application/pdf")},
            data={"model": "dpt-2-mini"},
            timeout=120,
        )

    if not response.ok:
        raise RuntimeError(
            f"LandingAI API call failed: {response.status_code} — "
            f"{response.text[:500]}"
        )

    logger.info("LandingAI API call succeeded for %s", pdf_path)
    return response.json()


# ---------------------------------------------------------------------------
# PyMuPDF text extraction
# ---------------------------------------------------------------------------

def extract_pymupdf_text(pdf_path: str) -> Dict[int, str]:
    """Extract text from each page of the PDF using PyMuPDF.

    Returns
    -------
    Dict[int, str]
        Text keyed by **1-indexed** page number.  Empty string for pages
        that return ``None``.
    """
    pages: Dict[int, str] = {}
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages[page_num + 1] = text if text is not None else ""

    doc.close()
    logger.info(
        "PyMuPDF extracted text from %d page(s) of %s", len(pages), pdf_path
    )
    return pages


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def ingest_pdf(pdf_path: str) -> Path:
    """Run the full ingestion pipeline on a single PDF.

    Parameters
    ----------
    pdf_path:
        Path to the input PDF file.

    Returns
    -------
    Path
        Path to the output ``_ingested.json`` file.
    """
    pdf = Path(pdf_path).resolve()
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    logger.info("Starting ingestion for: %s", pdf)

    # Step 1: LandingAI
    logger.info("Step 1/3 — Calling LandingAI API...")
    landingai_json = call_landingai(str(pdf))

    # Step 2: PyMuPDF
    logger.info("Step 2/3 — Extracting text with PyMuPDF...")
    pymupdf_pages = extract_pymupdf_text(str(pdf))

    # Step 3: Reconcile
    logger.info("Step 3/3 — Reconciling chunks...")
    reconciled = reconcile_document(landingai_json, pymupdf_pages)

    # Mark as reconciled
    reconciled["reconciled"] = True

    # Write output
    output_path = pdf.parent / f"{pdf.stem}_ingested.json"
    output_path.write_text(
        json.dumps(reconciled, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote reconciled output to: %s", output_path)

    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path-to-pdf>", file=sys.stderr)
        sys.exit(1)

    result = ingest_pdf(sys.argv[1])
    print(f"\nDone. Output: {result}")
