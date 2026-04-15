import json
import os
import sys
import re
import pdfplumber
from collections import defaultdict
from difflib import SequenceMatcher

# Add project root to sys.path to import pipeline modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from pipeline.gemini_client import generate, extract_json, MODEL_ROUTER
except ImportError:
    print("Warning: pipeline.gemini_client not found. LLM reconciliation will be skipped.")
    generate = None
    extract_json = None
    MODEL_ROUTER = None


# -----------------------------
# CONFIG & EXTRACTION
# -----------------------------

# Refined regex from user: requires first letter of title to be capital [A-Z]
COURSE_PATTERN = r'([A-Z]{2,4}\d{2})-(\d{3})\s+([A-Z].+?)(?=\s*(?:●|\bor\b\s+[A-Z]{2,4}\d{2}-\d{3}|[A-Z]{2,4}\d{2}-\d{3})|$)'

def extract_courses_from_pdf(catalog_path: str, output_path: str) -> dict:
    courses = defaultdict(list)
    print(f"Reading {catalog_path}...")
    with pdfplumber.open(catalog_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for match in re.finditer(COURSE_PATTERN, text, re.MULTILINE):
                    dept_code = match.group(1)
                    course_num = match.group(2)
                    raw_title = match.group(3).strip()
                    
                    key = f"{dept_code}-{course_num}"
                    courses[key].append(raw_title)
                    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(courses, f, indent=4)
        
    print(f"Extracted {len(courses)} unique course codes to {output_path}")
    return courses


# -----------------------------
# CLEANING CONFIG & FUNCTIONS
# -----------------------------

FLAG_KEYWORDS = [
    "prerequisite",
    "required for",
    "indicates that",
    "offered every",
    "recommended",
]

MAX_TITLE_LENGTH = 120  # beyond this is suspicious


def clean_title(title: str) -> str:
    """Basic normalization + cleanup"""
    # Remove trailing footnote numbers (e.g., "Business1", "I2", "Politics3")
    title = re.sub(r'([A-Za-z])(\d+)$', r'\1', title)

    # Remove standalone trailing numbers
    title = re.sub(r'\b\d+$', '', title)

    # Remove weird "(?)"
    title = title.replace("(?)", "")

    # Rule: If semicolon exists, drop it and anything follows
    if ";" in title:
        title = title.split(";")[0].strip()

    # Rule: Remove parentheticals starting with lowercase letter
    # e.g. "Biology (offered in spring only)" -> "Biology"
    # but keep "Biology (Capstone)"
    title = re.sub(r'\s*\([a-z].*?\)', '', title).strip()

    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title).strip()

    return title


def is_truncated(title: str) -> bool:
    """Detect likely truncated entries"""
    return (
        title.endswith("of") or
        title.endswith("and") or
        title.endswith("for") or
        title.endswith("with") or
        len(title.split()) < 2
    )


def needs_flagging(code: str, title: str, original_title: str) -> list:
    """Return reasons why a course should be flagged"""
    reasons = []
    lower = original_title.lower()

    # Non-course descriptions
    for kw in FLAG_KEYWORDS:
        if kw in lower:
            reasons.append(f"contains_keyword:{kw}")

    # Truncated
    if is_truncated(title):
        reasons.append("truncated")

    # Suspicious length
    if len(title) > MAX_TITLE_LENGTH:
        reasons.append("too_long")

    # Contains weird punctuation
    if "(?" in original_title or "..." in original_title:
        reasons.append("weird_characters")

    # Looks like a sentence
    if "," in original_title and len(original_title.split()) > 10:
        reasons.append("likely_description")

    return reasons


def normalize_for_matching(title: str) -> str:
    """Normalize title for cross-list detection"""
    title = title.lower()
    title = re.sub(r'[^a-z0-9\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


# -----------------------------
# CROSS-LIST DETECTION
# -----------------------------

def find_cross_listings(cleaned_courses):
    """
    Groups courses by normalized title
    """
    groups = defaultdict(list)

    for course in cleaned_courses:
        key = normalize_for_matching(course["title"])
        groups[key].append(course["code"])

    cross_listed = {}
    for key, codes in groups.items():
        if len(codes) > 1:
            for code in codes:
                cross_listed[code] = [c for c in codes if c != code]

    return cross_listed


# -----------------------------
# MAIN PIPELINE & VOTING LOGIC
# -----------------------------

def score_candidate(title: str, original_title: str) -> float:
    """Assigns a score to a single observation of a title"""
    score: float = 1.0
    lower = original_title.lower()

    # Penalize keywords strongly
    for kw in FLAG_KEYWORDS:
        if kw in lower:
            score -= 1.0

    if is_truncated(title):
        score -= 0.8

    if len(title) > MAX_TITLE_LENGTH:
        score -= 0.5

    if "(?" in original_title or "..." in original_title:
        score -= 0.5

    if "," in original_title and len(original_title.split()) > 10:
        score -= 0.5

    return score


class TitleCandidate:
    def __init__(self, original: str):
        self.score: float = 0.0
        self.count: int = 0
        self.original: str = original


def clean_course_data(raw_courses: dict):
    cleaned = []
    flagged = []

    for code, raw_titles in raw_courses.items():
        # If somehow passing dict with single string, wrap it
        if isinstance(raw_titles, str):
            raw_titles = [raw_titles]

        candidates = {}
        for rt in raw_titles:
            ct = clean_title(rt)
            val = score_candidate(ct, rt)
            if ct not in candidates:
                candidates[ct] = TitleCandidate(rt)
            candidates[ct].score += val
            candidates[ct].count += 1

        if not candidates:
            # Fallback
            continue

        # Sort candidates by total score descending
        sorted_candidates = sorted(candidates.items(), key=lambda x: x[1].score, reverse=True)
        winning_title, winner_data = sorted_candidates[0]

        total_occurrences = len(raw_titles)
        max_score = winner_data.score

        confidence = max_score / total_occurrences if total_occurrences > 0 else 0.0

        # We keep our flag reasons logic for the chosen winning title
        reasons = needs_flagging(code, winning_title, winner_data.original)
        if confidence < 0.5 or max_score <= 0:
            reasons.append(f"low_confidence_score:{confidence:.2f}")

        course_obj = {
            "code": code,
            "title": winning_title,
            "confidence": round(float(confidence), 3),
            "occurrences": total_occurrences,
            "candidate_scores": {k: round(float(v.score), 2) for k, v in sorted_candidates}
        }

        if reasons:
            course_obj["flag_reasons"] = reasons
            course_obj["reviewed"] = False
            flagged.append(course_obj)

        cleaned.append(course_obj)

    # Cross-list detection
    cross_map = find_cross_listings(cleaned)

    # Attach cross-list info and slightly boost confidence
    for course in cleaned:
        if course["code"] in cross_map:
            course["cross_listed_with"] = cross_map[course["code"]]
            course["confidence"] = round(min(1.0, float(course["confidence"]) + 0.2), 3)

    return {
        "cleaned_courses": cleaned,
        "flagged_courses": flagged,
    }


# -----------------------------
# OPTIONAL: FUZZY MATCH GROUPING
# -----------------------------

def fuzzy_group_courses(courses, threshold=0.9):
    groups = []
    used = set()

    for i, c1 in enumerate(courses):
        if c1["code"] in used:
            continue

        group = [c1["code"]]
        used.add(c1["code"])

        for j, c2 in enumerate(courses[i+1:], i+1):
            if c2["code"] in used:
                continue

            ratio = SequenceMatcher(
                None,
                c1["title"],
                c2["title"]
            ).ratio()

            if ratio >= threshold:
                group.append(c2["code"])
                used.add(c2["code"])

        if len(group) > 1:
            groups.append(group)

    return groups


# -----------------------------
# LLM RECONCILIATION
# -----------------------------

def reconcile_courses_with_llm(result_data: dict) -> dict:
    """
    Groups flagged courses and sends them to Gemini for reconciliation.
    Returns a clean mapping of code -> reconciled_title.
    """
    if not generate:
        print("Skipping LLM reconciliation (gemini_client not available).")
        return {c["code"]: c["title"] for c in result_data["cleaned_courses"]}

    flagged = result_data["flagged_courses"]
    if not flagged:
        print("No courses flagged for reconciliation.")
        return {c["code"]: c["title"] for c in result_data["cleaned_courses"]}

    print(f"Sending {len(flagged)} flagged courses to Gemini for reconciliation...")

    # Prepare input for LLM
    llm_input = []
    for c in flagged:
        llm_input.append({
            "code": c["code"],
            "current_title": c["title"],
            "candidates": c["candidate_scores"]
        })

    prompt = f"""
You are a university course catalog expert. Your task is to reconcile course titles that were flagged during extraction.
For each course below, look at the 'current_title' and the 'candidates' (which show other possible titles found in the PDF and their frequency/confidence scores).

Rules:
1. Select the most likely official, canonical course title.
2. Remove all instructional noise, notes, and artifacts.
   - Example: "Seminar (Note: these courses are offered only once per year)" -> "Seminar"
   - Example: "Marxisms (to be taken fall of ...)" -> "Marxisms"
   - Example: "Molecular and Cellular Foundations of Biology, and one ..." -> "Molecular and Cellular Foundations of Biology"
3. Remove parenthetical notes that start with lowercase letters (e.g., "(offered in spring)") but KEEP those that start with uppercase letters (e.g., "(Capstone)").
4. Output ONLY a valid JSON object mapping course codes to their reconciled titles.

COURSE DATA:
{json.dumps(llm_input, indent=2)}

RECONCILED JSON:
"""

    response_text = generate(prompt, model=MODEL_ROUTER)
    json_text = extract_json(response_text)
    
    try:
        reconciled_flagged = json.loads(json_text)
        print(f"Successfully reconciled {len(reconciled_flagged)} courses with LLM.")
    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        return {c["code"]: c["title"] for c in result_data["cleaned_courses"]}

    # Build final mapping
    final_mapping = {}
    for c in result_data["cleaned_courses"]:
        code = c["code"]
        if code in reconciled_flagged:
            final_mapping[code] = reconciled_flagged[code]
        else:
            final_mapping[code] = c["title"]

    return final_mapping


# -----------------------------
# RUN
# -----------------------------

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    catalog_path = os.path.join(script_dir, "../knowledge_base/2025-2027-southwestern-university-catalogpdf.pdf")
    courses_json_path = os.path.join(script_dir, "../knowledge_base/courses.json")
    cleaned_courses_path = os.path.join(script_dir, "../knowledge_base/cleaned_courses.json")

    # 1. Load or Extract courses
    # If the file is missing or contains old format mapping, re-extract
    raw_courses = None
    if os.path.exists(courses_json_path):
        with open(courses_json_path, "r", encoding="utf-8") as f:
            data_load = json.load(f)
            
        # Check if it is the raw (dict of lists) or final (dict of strings)
        is_list_format = False
        for v in data_load.values():
            if isinstance(v, list):
                is_list_format = True
                break
        
        if is_list_format:
            print(f"Loading existing raw occurrences from {courses_json_path}")
            raw_courses = data_load
        else:
            print("courses.json is in final format. Forcing re-extraction to get raw candidates.")
            raw_courses = extract_courses_from_pdf(catalog_path, courses_json_path)
    else:
        raw_courses = extract_courses_from_pdf(catalog_path, courses_json_path)

    # 2. Voting Stage
    print("Step 1: Running consensus voting...")
    result = clean_course_data(raw_courses)

    # 3. LLM Stage
    print("Step 2: Starting Gemini reconciliation...")
    final_mapping = reconcile_courses_with_llm(result)

    # 4. Save results
    with open(cleaned_courses_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    with open(courses_json_path, "w", encoding="utf-8") as f:
        json.dump(final_mapping, f, indent=4)

    print(f"\nPipeline complete.")
    print(f"Final reconciled mapping saved to {courses_json_path}")
    print(f"Flagged items handled: {len(result['flagged_courses'])}")