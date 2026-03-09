"""
clean_chunks.py
===============
Text reconciliation between LandingAI markdown chunks and PyMuPDF ground-truth
text.  Three functions:

    clean_text          – normalize text for comparison (strip markdown, collapse
                          whitespace, lowercase)
    reconcile_chunk     – compare a single chunk's text against page ground truth
    reconcile_document  – walk a full LandingAI JSON and reconcile every chunk
"""

from __future__ import annotations

import copy
import logging
import re
from difflib import SequenceMatcher
from typing import Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns for clean_text
# ---------------------------------------------------------------------------

# Markdown heading markers at the start of a line: # ## ### etc.
_RE_HEADING = re.compile(r"^#{1,6}\s*", re.MULTILINE)

# Bold / italic markers: **, *, __, _  (only when used as formatting wraps)
_RE_BOLD_ITALIC = re.compile(r"(?<!\w)[*_]{1,3}|[*_]{1,3}(?!\w)")

# Inline code backticks
_RE_BACKTICK = re.compile(r"`+")

# Blockquote markers at the start of a line
_RE_BLOCKQUOTE = re.compile(r"^>\s*", re.MULTILINE)

# List-item dashes at the start of a line (only the marker dash)
_RE_LIST_DASH = re.compile(r"^-\s+", re.MULTILINE)

# Soft hyphens and zero-width characters
_RE_INVISIBLE = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff]")

# Collapse all whitespace runs to single space
_RE_WHITESPACE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Strip markdown formatting so LandingAI and PyMuPDF text can be compared
    on equal footing.

    Operations:
        1. Remove markdown heading markers (``#``)
        2. Remove bold/italic markers (``*``, ``_``)
        3. Remove inline-code backticks
        4. Remove blockquote markers (``>``)
        5. Remove list-item dashes used as formatting
        6. Remove soft hyphens and zero-width characters
        7. Collapse all whitespace to a single space
        8. Strip leading/trailing whitespace
        9. Lowercase

    Punctuation and digits are **not** removed — they are semantically
    meaningful (e.g. course IDs like ``54-284``).
    """
    t = text
    t = _RE_HEADING.sub("", t)
    t = _RE_BOLD_ITALIC.sub("", t)
    t = _RE_BACKTICK.sub("", t)
    t = _RE_BLOCKQUOTE.sub("", t)
    t = _RE_LIST_DASH.sub("", t)
    t = _RE_INVISIBLE.sub("", t)
    t = _RE_WHITESPACE.sub(" ", t)
    t = t.strip()
    t = t.lower()
    return t


def reconcile_chunk(chunk_text: str, page_ground_truth: str) -> str:
    """Compare one chunk's markdown text against the PyMuPDF ground-truth text
    for the same page.  Return either the original markdown (if the content
    matches) or the ground-truth substring (if a discrepancy is found).

    Strategy
    --------
    1. Clean both strings (strip markdown, lowercase, collapse whitespace).
    2. Try exact substring match of the cleaned chunk within the cleaned page.
    3. On failure, fall back to a sliding-window character-level alignment
       using :class:`difflib.SequenceMatcher`.

    TODO: remove 4 and 5
    Reconcile chunk should replace the chunk with the ground-truth window if the
    best-match ratio is not 1.0

    4. If the best-match ratio ≥ 0.95 → no discrepancy → return *original*
       ``chunk_text`` (preserving markdown).
    5. If the best-match ratio < 0.95 → discrepancy detected → return the
       ground-truth window and log a WARNING.
    """
    cleaned_chunk = clean_text(chunk_text)
    cleaned_page = clean_text(page_ground_truth)

    if not cleaned_chunk:
        return chunk_text  # nothing to compare

    # --- Exact substring match ---
    idx = cleaned_page.find(cleaned_chunk)
    if idx != -1:
        # Content is identical after cleaning — no discrepancy
        return chunk_text

    # --- SequenceMatcher-based alignment ---
    #
    # Instead of brute-force sliding a window at every character position
    # (O(n·m²)), run SequenceMatcher once on the full strings to find the
    # matching blocks, derive the best alignment offset, extract one window,
    # and score that window.
    #
    window_len = len(cleaned_chunk)
    if window_len == 0 or len(cleaned_page) == 0:
        return chunk_text

    if len(cleaned_page) < window_len:
        # Chunk is longer than the page — compare directly
        ratio = SequenceMatcher(None, cleaned_chunk, cleaned_page).ratio()
        if ratio < 0.95:
            logger.warning(
                "Chunk longer than page ground truth.  ratio=%.3f\n"
                "  chunk : %.80s\n"
                "  page  : %.80s",
                ratio,
                cleaned_chunk[:80],
                cleaned_page[:80],
            )
            return cleaned_page
        return chunk_text

    # Run SequenceMatcher once on chunk vs full page to find matching blocks.
    sm = SequenceMatcher(None, cleaned_chunk, cleaned_page, autojunk=False)
    blocks = sm.get_matching_blocks()

    if not blocks or (len(blocks) == 1 and blocks[0].size == 0):
        # No meaningful match at all
        logger.warning(
            "No matching blocks found for chunk in page.\n"
            "  chunk : %.80s",
            cleaned_chunk[:80],
        )
        return chunk_text

    # Compute alignment offset from the largest matching block:
    # If block matches chunk[a:a+size] to page[b:b+size], then the chunk
    # likely starts at page[b - a].
    best_block = max(blocks, key=lambda b: b.size)
    estimated_start = best_block.b - best_block.a

    # Clamp to valid range
    max_start = len(cleaned_page) - window_len
    estimated_start = max(0, min(estimated_start, max_start))

    # Extract the window and score it
    gt_window = cleaned_page[estimated_start : estimated_start + window_len]
    ratio = SequenceMatcher(
        None, cleaned_chunk, gt_window, autojunk=False
    ).ratio()

    if ratio >= 1:
        # Close enough — preserve original markdown
        return chunk_text

    # Discrepancy detected — return the ground-truth window
    logger.warning(
        "Discrepancy detected (ratio=%.3f).\n"
        "  chunk_text  : %.80s\n"
        "  ground_truth: %.80s",
        ratio,
        cleaned_chunk[:80],
        gt_window[:80],
    )
    return gt_window


def reconcile_document(
    landingai_json: dict, pymupdf_pages: Dict[int, str]
) -> dict:
    """Walk all chunks in a LandingAI JSON response and reconcile each chunk's
    ``markdown`` text against the corresponding PyMuPDF page text.

    Parameters
    ----------
    landingai_json:
        The full JSON dict returned by the LandingAI agentic-document-analysis
        API.  Expected to contain a top-level ``"chunks"`` list where each
        chunk has ``"markdown"`` (str) and ``"grounding"."page"`` (int,
        0-indexed).
    pymupdf_pages:
        Ground-truth text keyed by **1-indexed** page number (i.e. what
        ``fitz.Page.get_text("text")`` returns for each page).

    Returns
    -------
    dict
        A deep copy of *landingai_json* with each chunk's ``"markdown"`` field
        potentially replaced by ground-truth text where discrepancies were
        found.
    """
    result = copy.deepcopy(landingai_json)

    chunks = result.get("chunks", [])
    total = len(chunks)
    reconciled_count = 0

    for i, chunk in enumerate(chunks):
        markdown = chunk.get("markdown", "")
        if not markdown:
            continue

        # LandingAI pages are 0-indexed; pymupdf_pages are 1-indexed
        page_0 = chunk.get("grounding", {}).get("page", -1)
        page_1 = page_0 + 1  # convert to 1-indexed

        page_gt = pymupdf_pages.get(page_1, "")
        if not page_gt:
            logger.debug(
                "No PyMuPDF text for page %d (chunk %d/%d), skipping.",
                page_1, i + 1, total,
            )
            continue

        new_text = reconcile_chunk(markdown, page_gt)

        if new_text != markdown:
            chunk["markdown"] = new_text
            reconciled_count += 1

    logger.info(
        "Reconciliation complete: %d/%d chunks updated.", reconciled_count, total
    )
    return result
