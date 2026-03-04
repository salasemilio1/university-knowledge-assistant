"""
Step 1: Parse and Clean LandingAI JSON
=======================================
Loads raw LandingAI extraction JSON, drops marginalia chunks, strips nav/footer
noise, normalizes OCR artifacts, and returns clean structured dicts ready for
downstream pipeline stages.
"""

import json
import re
from pathlib import Path
from collections import Counter


# ---------------------------------------------------------------------------
# Regex patterns compiled once for performance
# ---------------------------------------------------------------------------

# LandingAI anchor tags: <a id='...'>...</a>  (content between tags is usually empty)
RE_ANCHOR_TAG = re.compile(r"<a\s+id=['\"][^'\"]*['\"]>\s*</a>")

# Timestamp bleed from browser print header, e.g. "3/4/26, 10:31 AM"
RE_TIMESTAMP = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*[AP]M")

# URLs (http or https)
RE_URL = re.compile(r"https?://\S+")

# Page-number indicators like "1/5", "2/5" — only when they are the entire line
RE_PAGE_NUMBER = re.compile(r"^\d+/\d+$", re.MULTILINE)

# Nav-bar / header bleed patterns (order matters — longest first)
NAV_PATTERNS = [
    "Menu Search Apply Visit Majors & Minors",
    "Apply Visit Majors & Minors",
    "Menu Search",
]

# Page title bleed
PAGE_TITLE = "Courses • Southwestern University"

# OCR normalization map  (pattern → replacement)
OCR_FIXES = {
    "Pre requisite": "Prerequisite",   # erroneous space in "Prerequisite"
    "Pre requisites": "Prerequisites",
}

# Collapse runs of 3+ newlines into exactly 2 (one blank line)
RE_MULTI_NEWLINE = re.compile(r"\n{3,}")

# HTML page-break comment
RE_PAGE_BREAK = re.compile(r"<!--\s*PAGE BREAK\s*-->")


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _clean_text(raw_markdown: str) -> str:
    """Apply all cleaning transformations to a single chunk's markdown."""
    text = raw_markdown

    # 1. Strip anchor tags
    text = RE_ANCHOR_TAG.sub("", text)

    # 2. Strip page-break comments
    text = RE_PAGE_BREAK.sub("", text)

    # 3. Strip timestamps
    text = RE_TIMESTAMP.sub("", text)

    # 4. Strip page-title bleed
    text = text.replace(PAGE_TITLE, "")

    # 5. Strip URLs
    text = RE_URL.sub("", text)

    # 6. Strip page numbers (full-line only)
    text = RE_PAGE_NUMBER.sub("", text)

    # 7. Strip nav-bar patterns (longest first to avoid partial matches)
    for nav in NAV_PATTERNS:
        text = text.replace(nav, "")

    # 8. Normalize OCR artifacts
    for bad, good in OCR_FIXES.items():
        text = text.replace(bad, good)

    # 9. Collapse excessive blank lines and trim
    text = RE_MULTI_NEWLINE.sub("\n\n", text)
    text = text.strip()

    return text


def parse_landingai_json(filepath: str) -> list[dict]:
    """
    Parse a LandingAI extraction JSON file and return cleaned chunks.

    Parameters
    ----------
    filepath : str
        Path to the `*.extraction.json` file.

    Returns
    -------
    list[dict]
        Each dict contains:
        - id   (str)  : original chunk UUID
        - text (str)  : cleaned text content
        - page (int)  : zero-indexed page number
        - bbox (dict) : bounding box {left, top, right, bottom}
    """
    raw = json.loads(Path(filepath).read_text(encoding="utf-8"))
    chunks = raw.get("chunks", [])

    results = []
    for chunk in chunks:
        # --- Drop marginalia ---
        if chunk.get("type") == "marginalia":
            continue

        raw_md = chunk.get("markdown", "")
        cleaned = _clean_text(raw_md)

        # Drop chunks that are empty after cleaning (pure nav-only chunks)
        if not cleaned:
            continue

        grounding = chunk.get("grounding", {})
        results.append({
            "id":   chunk["id"],
            "text": cleaned,
            "page": grounding.get("page", -1),
            "bbox": grounding.get("box", {}),
        })

    return results


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_step1(results: list[dict]) -> None:
    """
    Validate Step 1 output and print a human-readable summary.

    Checks
    ------
    1. No marginalia chunks remain (cannot verify type directly, but we check
       for tell-tale marginalia content).
    2. No anchor tags remain in any text field.
    3. No known nav strings appear in any text field.
    """
    print("=" * 60)
    print("STEP 1 VALIDATION")
    print("=" * 60)

    all_passed = True

    # Check 1: no anchor tags
    anchor_hits = [r["id"] for r in results if "<a id=" in r["text"]]
    if anchor_hits:
        print(f"  FAIL  Anchor tags found in {len(anchor_hits)} chunk(s): {anchor_hits[:3]}")
        all_passed = False
    else:
        print("  PASS  No anchor tags remain")

    # Check 2: no nav strings
    nav_needles = ["Menu Search", "Apply Visit"]
    for needle in nav_needles:
        hits = [r["id"] for r in results if needle in r["text"]]
        if hits:
            print(f"  FAIL  Nav string '{needle}' found in {len(hits)} chunk(s): {hits[:3]}")
            all_passed = False
        else:
            print(f"  PASS  No '{needle}' strings remain")

    # Check 3: no timestamp patterns
    ts_hits = [r["id"] for r in results if RE_TIMESTAMP.search(r["text"])]
    if ts_hits:
        print(f"  FAIL  Timestamps found in {len(ts_hits)} chunk(s): {ts_hits[:3]}")
        all_passed = False
    else:
        print("  PASS  No timestamp patterns remain")

    # Check 4: no URL patterns
    url_hits = [r["id"] for r in results if RE_URL.search(r["text"])]
    if url_hits:
        print(f"  FAIL  URLs found in {len(url_hits)} chunk(s): {url_hits[:3]}")
        all_passed = False
    else:
        print("  PASS  No URL patterns remain")

    # Check 5: no page-number-only content
    pn_hits = [r["id"] for r in results if RE_PAGE_NUMBER.search(r["text"])]
    if pn_hits:
        print(f"  FAIL  Page numbers found in {len(pn_hits)} chunk(s): {pn_hits[:3]}")
        all_passed = False
    else:
        print("  PASS  No page-number patterns remain")

    # --- Summary ---
    print()
    print(f"Total cleaned chunks: {len(results)}")

    page_counts = Counter(r["page"] for r in results)
    for page in sorted(page_counts):
        print(f"  Page {page}: {page_counts[page]} chunk(s)")

    print()
    print("First 3 cleaned texts (truncated to 200 chars):")
    print("-" * 60)
    for i, r in enumerate(results[:3]):
        preview = r["text"][:200].replace("\n", "\\n")
        print(f"  [{i}] id={r['id'][:8]}... page={r['page']}")
        print(f"      {preview}")
        print()

    if all_passed:
        print("ALL CHECKS PASSED ✓")
    else:
        print("SOME CHECKS FAILED ✗")

    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    default_path = (
        Path(__file__).resolve().parent.parent
        / "Courses___Southwestern_University.extraction.json"
    )
    filepath = sys.argv[1] if len(sys.argv) > 1 else str(default_path)

    print(f"Loading: {filepath}")
    results = parse_landingai_json(filepath)

    # print first 5 results
    print(f"Results: {results[0:5]}")
    #validate_step1(results)
