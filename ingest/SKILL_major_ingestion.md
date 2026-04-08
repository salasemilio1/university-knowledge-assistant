# SKILL: Major Skills File Generator
# Southwestern University — Knowledge Assistant Ingestion Pipeline
# Version: 2.0
# Last Updated: 2026-03-18

---

## Purpose

This skill guides a frontier AI model (Claude Sonnet or Opus recommended) through
the process of reading extracted text files from a university major's document
corpus and producing a structured `skills_index.md` file for that major.

The `skills_index.md` is the backbone of the inference pipeline. It is the ONLY
file the routing model reads before deciding which documents to retrieve. Everything
downstream — routing accuracy, answer quality, fallback behavior — depends on the
quality of this file. Treat its generation as the highest-value step in the system.

---

## System Context

### Architecture Overview

This skills file is part of a two-phase AI knowledge assistant built for
Southwestern University students.

**Phase 1 — Ingestion (this skill)**
A frontier model reads all `.txt` files for a given major and produces a
`skills_index.md`. This runs once, offline, and is regenerated only when
source documents are updated.

**Phase 2 — Inference (downstream)**
When a student asks a question, the inference model:
1. Reads the `skills_index.md` for the student's major
2. Makes a routing decision: which 1-3 `.txt` files contain the answer
3. Loads those files into context
4. Answers the student's question with citations

The routing model reads the skills index cold — it has no memory of previous
queries and no access to the raw documents at routing time. Every routing
decision lives or dies on the quality of this index.

### File System Layout

```
/knowledge_base
  /<major_slug>                    ← e.g., computer_science
    skills_index.md                ← The output of using this skills file to create new skills for each major
    /docs
      /raw                         ← original PDFs (source of truth)
      /extracted                   ← .txt files (input to ingestion)
  /general                         ← university-wide academic policies (SU_General_Policies.txt)
    skills_index.md
    /docs
      /raw
      /extracted
  /financial                       ← financial aid, tuition, fees, and student resources (SU_Resources_and_Financial.txt)
    skills_index.md
    /docs
      /raw
      /extracted
```

### Known General Documents (Always Available for Cross-Reference)

Two university-wide documents have already been ingested and apply to ALL majors:

- **`SU_General_Policies.txt`** — 2025-2027 catalog. Covers: accreditation, Paideia curriculum, degree types (B.A., B.S., B.F.A., B.Mus., B.S.Ed.), all graduation requirements, academic rights, grading system (including Pass/D/F), attendance, registration deadlines, academic honors (Dean's List, Latin Praise, Departmental Honors, Paideia with Distinction), withdrawals, academic probation/dismissal/appeal procedures, transfer credit rules, credit by examination (AP, IB, CAPE, CLEP), language placement, and the course numbering system.

- **`SU_Resources_and_Financial.txt`** — Covers: study abroad programs (London Semester, ISEP Exchange, NYAP, CHIP, CYA), funded internships (SURF, King Creativity Fund), health professions shadowing programs, financial aid, tuition and fee schedules, billing and payment procedures, tuition refund schedule, financial aid impact of withdrawal, and campus resources.

When generating a major's `skills_index.md`, **always include cross-reference flags** (Section 7) pointing to these documents for any topic they cover that the major documents do not fully address.

### Input Format

The model receives `.txt` files extracted from PDFs via `pdfplumber`.
Each file has page separators in the format:

```
--- Page N of Total ---

[page content]
```

Tables may be imperfectly formatted. Course numbers, credit hours, and
prerequisite chains are the most critical data — verify them carefully
against surrounding context when the table formatting looks degraded.

---

## Ingestion Prompt

Use the following prompt verbatim when calling the frontier model. Replace
bracketed placeholders before sending.

---

```
You are an expert academic document analyst building a structured index for
a university AI knowledge assistant at Southwestern University in Georgetown, Texas.

Your task is to read all provided documents for the [MAJOR_NAME] department
and produce a `skills_index.md` file in the exact format specified below.

This index will be used by an AI routing model that has NO access to the
original documents. The routing model reads ONLY this index, then decides
which documents to retrieve. If a topic, course, or policy is not captured
here, the system cannot retrieve it. Omissions are silent failures.

Be exhaustive. Be specific. Use exact course numbers, credit hour counts,
and policy language from the documents. Do not generalize when exact
information is available.

--- INPUT DOCUMENTS ---

[DOCUMENT 1]
Filename: [exact_filename.txt]
[full extracted text content]

[DOCUMENT 2]
Filename: [exact_filename.txt]
[full extracted text content]

[... repeat for all documents ...]

--- END DOCUMENTS ---

Produce the skills_index.md now, following this structure exactly:

════════════════════════════════════════════════════════
SECTION 1 — METADATA BLOCK
════════════════════════════════════════════════════════

# Skills Index — [MAJOR_NAME]
**Institution:** Southwestern University, Georgetown, Texas
**Last Ingested:** [DATE]
**Ingestion Model:** [MODEL_NAME]
**Document Count:** [N]
**Degree Paths Covered:** [e.g., B.A., B.S., B.F.A., B.Mus., B.S.Ed., Minor — use only those applicable to this major]

---

════════════════════════════════════════════════════════
SECTION 2 — DOCUMENT REGISTRY
════════════════════════════════════════════════════════

For EVERY .txt file provided, produce one entry in this format.
Do not skip any file. The filename must match exactly as provided.

### [Human-Readable Document Title]
- **filename:** `exact_filename.txt`
- **document_type:** [one of: requirements | course_info | policy | advising | calendar | financial | general | resources]
- **degree_relevance:** [one or more of: B.S. | B.A. | Minor | All | General]
- **time_sensitive:** [true | false]
- **catalog_year:** [e.g., 2024-2025 — or "N/A" if not time-sensitive]
- **description:** [5-7 sentences. Be specific. Name the actual courses,
  requirement categories, policies, credit hour counts, and GPA thresholds
  mentioned. A generic description like "covers CS requirements" is a failure.
  A good description names every major section of the document.]
- **critical_data:** [Bullet list of the most important specific facts in this
  document — things a student would directly ask about. Examples: total credit
  hours, specific required courses, GPA cutoffs, deadlines, named policies.]
- **retrieval_triggers:** [10-15 short phrases that represent student queries
  this document can answer. These are used by the routing model for fuzzy
  matching. Write them as a student would say them, not as a librarian would
  catalog them. Examples: "how many credits to graduate", "do I need calc",
  "what counts as an elective"]

---

════════════════════════════════════════════════════════
SECTION 3 — DEGREE PATH SUMMARIES
════════════════════════════════════════════════════════

Write a structured summary for each degree path available in this major.
This section is the most frequently retrieved section for broad advising
questions. Be complete — do not omit any requirement category.

### SU Universal Graduation Requirements (All Degree Paths)

These apply to ALL students regardless of major. Always include this block.
Source: `SU_General_Policies.txt`

| Requirement | Detail |
|---|---|
| Minimum Total Credits | 127 credits |
| Minimum SU Residency Credits | 64 credits (last 32 must be in-residence) |
| Minimum Overall GPA | 2.000 (both cumulative and SU-only) |
| Minimum Major GPA | 2.000 average (no grade below C- counts toward major) |
| Major Residency Requirement | At least 60% of major credits at SU |
| Minor Residency Requirement | At least 12 credits at SU (if minor pursued) |
| Graduation Application | "Application for Diploma" must be filed; financial holds block diploma |
| Degree Conferral Dates | December, May, August only; Commencement held once per year in May |

### SU Universal Curriculum Requirements (Paideia Framework)

SU's general education model is called **Paideia**. Every major's degree plan is built on top of these shared requirements. Always note which Paideia requirements the major's courses satisfy.

**Required for ALL degree paths (B.A., B.S., B.F.A., B.Mus., B.S.Ed.):**
- First-Year Seminar (FYS) or Advanced-Entry Seminar (AES): 4 credits
- Languages and Cultures: through third-semester proficiency (up to 12 credits; satisfied by placement exam, transfer credit, or SU coursework through level XX-164)
- Fitness and Recreational Activity (FRA): 1 credit (one season of intercollegiate athletics may satisfy this)
- Power and Justice (PJ) course: 1 course, 3-4 credits — **cannot be satisfied by transfer credit**
- Exploration and Breadth: 6 courses from outside the major (18-24 credits), distributed as:
  - Part I: one course from each of four areas: Fine Arts (FA), Humanities (H), Natural Sciences (NS), Social Sciences (ScS)
  - Part II: one additional course from two of the four areas

**Additional Requirements for B.S. only** (if not required in the major):
- Biology (50-173/171 or 50-183/181): 4 credits
- Chemistry (51-103/101): 4 credits
- Mathematics (52-164): 4 credits
- Physics (53-154): 4 credits
- Two approved courses from different disciplines in the Natural Sciences Area completing year-long sequences: 8 credits
- At least two additional course requirements in Natural Sciences Area or Psychology: credits vary

**B.S. Restriction:** The first (or only) major must come from the Natural Sciences Area or Psychology.

**Paideia with Distinction** (optional, not required for graduation):
Students who complete a Paideia seminar, present at the Research and Creative Works Symposium, and complete one intensive Paideia option (Paideia Minor OR two approved Paideia experiences) earn this distinction. Apply sophomore/junior year. Deadlines: November 15 for December graduates, April 15 for May/August graduates.

---

For each degree path (B.A., B.S., B.F.A., B.Mus., B.S.Ed., Minor, etc.) offered in this major:

### [Degree Path Name] — e.g., B.S. in Computer Science

| Field | Detail |
|---|---|
| Total Credit Hours | |
| Major Credit Hours | |
| Minimum GPA (Overall) | |
| Minimum GPA (Major) | |
| Residency Requirement | |
| Source Document | `filename.txt` |

**Required Core Courses:**
List every required course with course number, full name, and credit hours.
Example: CSCI 1320 — Introduction to Programming (3 hrs)

**Required Supporting Courses (Math, Science, etc.):**
[same format]

**Elective Requirements:**
- How many credit hours of electives required:
- Pool of eligible courses (list all, with numbers):
- Any restrictions on elective selection:

**Concentration or Track Options (if any):**
[describe each track and its specific requirements]

**Additional Graduation Requirements:**
[capstone, internship, portfolio, senior seminar, etc.]

**Notable Constraints:**
[anything unusual — time limits, sequential requirements, GPA gates, etc.]

---

Repeat the above block for every degree path. Then add:

### Key Differences Between Degree Paths

This subsection is REQUIRED and must be explicit. The most common student
routing failure is a question about "the CS degree" without specifying B.S.
vs B.A. The routing model must be able to identify when this disambiguation
is needed.

- List every meaningful difference between the B.S. and B.A. (or other paths)
- Include: credit hour differences, required courses that differ, elective
  flexibility differences, math/science requirement differences
- Note which path is more common or recommended for specific career goals
  if the documents indicate this

---

════════════════════════════════════════════════════════
SECTION 4 — COURSE INDEX
════════════════════════════════════════════════════════

List every course mentioned across ALL documents. This section is retrieved
when a student asks about a specific course. Accuracy of prerequisites is
critical — an error here directly harms student scheduling decisions.

For each course:

### CSCI XXXX — [Course Name]
- **Credit Hours:** 
- **Prerequisites:** [list exactly as stated in documents, or "None"]
- **Corequisites:** [if any, or "None"]
- **Offered:** [Fall | Spring | Both | Unknown]
- **Required For:** [which degree paths require this course]
- **Counts As:** [requirement category it satisfies — e.g., "Core requirement", "Upper-division elective"]
- **Notes:** [any enrollment restrictions, lab components, special considerations]
- **Source:** `filename.txt`

Group courses by prefix if multiple prefixes exist (e.g., CSCI, MATH, PHYS).

**SU Course Numbering System:** SU uses a 5-digit system where the first two digits are the department code, digits 3-4 are the course number (0-19 = introductory; 20-89 = upper-level; 90+ = advanced special offerings), and digit 5 is the credit hours (0 = zero-credit). Example: `CSCI 1324` = CS dept, course 13, 4 credits. Applied Music uses a different format (e.g., APM8A-001). Lab courses show lecture/lab hours as (3-3) after the course number.

---

════════════════════════════════════════════════════════
SECTION 5 — TOPIC INDEX
════════════════════════════════════════════════════════

This is the primary routing lookup table. The routing model scans this
section to match a student query to relevant documents.

Produce 50-80 entries. Err on the side of more. Granularity matters —
"elective requirements" and "upper-division elective requirements" are
different topics and may map to different documents.

Format each entry as:
- [specific topic] → `filename.txt` [, `filename2.txt` if multiple]

Required topic categories to cover at minimum:
- All degree path variations and differences
- Every named requirement category from every degree path
- All individual required courses (by course number AND by name)
- Course substitution and waiver policies
- Transfer credit evaluation (note: C- minimum required; P/CR grades not accepted; transfer credits use ELEC-0XX or ELEC-3XX codes)
- GPA requirements — overall (2.000), major GPA (2.000), GPA for honors
- Academic standing, probation, dismissal
- Graduation application process and timeline
- Prerequisite chains for upper-division courses
- Double major / dual degree policies (note: paired majors cannot be declared individually as double majors)
- Adding or dropping the minor
- Senior capstone or culminating requirement
- Advising requirements and appointment processes (note: one meeting per semester required)
- Course repeat policies
- Pass/D/F grading options (SU uses Pass/D/F — NOT simply Pass/Fail)
- Incomplete grade policies
- Academic calendar and registration deadlines (add/drop through 8th class day; drop with W through end of week 10)
- Study abroad credit applicability (up to 19 credits per semester; must work through SAISS)
- Internship or experiential learning credit
- Paideia curriculum requirements (FYS/AES, Language & Cultures, Power and Justice, FRA, Exploration & Breadth)
- Paideia with Distinction (optional honor — seminar + Symposium presentation + intensive option)
- Credit by examination (AP scores of 4-5; IB score of 5+ on higher-level; CAPE scores of 1-2; CLEP; departmental advanced standing)
- Language placement exemption process
- Financial holds and their impact on registration, transcripts, and diplomas
- Tuition refund schedule (80%/60%/50%/40%/30%/0% by week)
- Study abroad programs available (London Semester, ISEP Exchange, NYAP, CHIP, College Year in Athens)
- SURF and faculty-mentored research opportunities

---

════════════════════════════════════════════════════════
SECTION 6 — QUERY PATTERN MAP
════════════════════════════════════════════════════════

Generate 35 realistic student questions. These give the routing model
concrete examples to reason against. Cover the full student lifecycle
and all degree paths. Include ambiguous questions that require
disambiguation.

For each entry:

**Q:** [the student's question, written naturally as a student would ask it]
**Docs:** `filename.txt` [, `filename2.txt`]
**Routing Note:** [one sentence: what in the index led to this routing decision,
and what part of the document answers it]
**Disambiguation Needed:** [Yes/No — if Yes, what must the system clarify before answering]

Cover questions from each of these student profiles:
- Incoming freshman (first semester, no prior coursework)
- Sophomore deciding between B.S. and B.A.
- Junior considering adding the minor
- Senior applying for graduation
- Transfer student evaluating credit applicability
- Student who failed or withdrew from a required course
- Student considering a double major
- Student with an academic hold or GPA concern
- Student asking about a specific course (at least 5 course-specific questions)
- Student asking a question where the answer requires BOTH the major doc
  AND a general university policy doc (at least 3 such questions)

---

════════════════════════════════════════════════════════
SECTION 7 — CROSS-REFERENCE FLAGS
════════════════════════════════════════════════════════

List every topic where this major's documents are INCOMPLETE and a complete
answer requires consulting the /general or /financial university policy documents.

The following cross-reference flags are REQUIRED for every major's skills index,
because these topics are covered only in the university-wide documents:

**Always present (standard flags for all majors):**

- **Topic:** Graduation requirements (credit minimums, residency, GPA)
  - **What major docs cover:** Major-specific credit hours and courses
  - **What general docs must cover:** 127-credit minimum, 64-credit SU residency, last 32 in-residence, 2.000 GPA, 60% major residency, Application for Diploma process
  - **Routing instruction:** Always retrieve `SU_General_Policies.txt` alongside major requirements doc for any graduation eligibility question

- **Topic:** Paideia general education requirements
  - **What major docs cover:** Which major courses satisfy Paideia areas (FA, H, NS, ScS, PJ)
  - **What general docs must cover:** Full structure of FYS/AES, Language & Cultures, FRA, Power and Justice, Exploration & Breadth Parts I and II, Paideia with Distinction
  - **Routing instruction:** Always retrieve `SU_General_Policies.txt` for any question about gen-ed, breadth requirements, or Paideia

- **Topic:** Pass/D/F grading option
  - **What major docs cover:** May note restrictions (e.g., courses that cannot be taken P/D/F)
  - **What general docs must cover:** Full Pass/D/F policy, deadlines to switch, GPA impact
  - **Routing instruction:** Retrieve `SU_General_Policies.txt` for any grading option question

- **Topic:** Academic probation, dismissal, and appeal
  - **What major docs cover:** Typically not covered
  - **What general docs must cover:** Good Standing definition, Warning, Probation, Dismissal thresholds, Academic Standards Committee appeal process
  - **Routing instruction:** Always retrieve `SU_General_Policies.txt`

- **Topic:** Transfer credit rules
  - **What major docs cover:** May specify which transfer courses count toward major
  - **What general docs must cover:** C- minimum required; P/CR grades not accepted; ELEC-0XX/3XX coding; 60% major residency rule; AP/IB/CAPE/CLEP policies
  - **Routing instruction:** Retrieve both major doc and `SU_General_Policies.txt`

- **Topic:** Study abroad credit and programs
  - **What major docs cover:** May note study abroad applicability to major
  - **What general docs must cover:** SAISS process, approved programs (London, ISEP, NYAP, CHIP, CYA), deadlines, up to 19 transfer credits per semester, financial aid applicability
  - **Routing instruction:** Retrieve `SU_Resources_and_Financial.txt` for program details; retrieve `SU_General_Policies.txt` for credit transfer rules

- **Topic:** Financial aid impact of credit load changes or withdrawal
  - **What major docs cover:** Not covered
  - **What general docs must cover:** Withdrawal and financial aid impact, tuition refund schedule, part-time financial aid thresholds
  - **Routing instruction:** Always retrieve `SU_Resources_and_Financial.txt`

- **Topic:** Tuition refund schedule
  - **What major docs cover:** Not covered
  - **What general docs must cover:** 80%/60%/50%/40%/30%/0% by week; summer refund schedule; room no-refund rule
  - **Routing instruction:** Always retrieve `SU_Resources_and_Financial.txt`

- **Topic:** Internship and experiential learning opportunities
  - **What major docs cover:** Major-specific internship requirements or courses
  - **What general docs must cover:** Academic vs. funded internship distinction, SURF, King Creativity Fund, health professions shadowing (St. David's, Houston Methodist), NYAP, CHIP
  - **Routing instruction:** Retrieve `SU_Resources_and_Financial.txt` for program details

- **Topic:** Latin Honors and Paideia with Distinction
  - **What major docs cover:** May reference Departmental Honors (thesis/project)
  - **What general docs must cover:** Cum Laude/Magna Cum Laude/Summa Cum Laude GPA thresholds, Dean's List criteria, Paideia with Distinction requirements and deadlines
  - **Routing instruction:** Always retrieve `SU_General_Policies.txt`

- **Topic:** Disability accommodations and course substitution
  - **What major docs cover:** Not covered
  - **What general docs must cover:** Services for Students with Disabilities, ADA accommodations, disability-related course substitution policy and appeals
  - **Routing instruction:** Always retrieve `SU_General_Policies.txt`; direct student to SSD office

For each flag:

- **Topic:** [topic name]
- **What major docs cover:** [what partial information exists in major docs]
- **What general docs must cover:** [what is missing and must come from /general or /financial]
- **Routing instruction:** [e.g., "Always retrieve both `cs_requirements.txt`
  AND `SU_General_Policies.txt` when this topic appears in a query"]

Additional cross-reference flags to watch for beyond the standard set above:
- Grade appeal procedures
- Leave of absence policies
- Veterans benefits and enrollment certification
- Course repeat policies (and GPA recalculation rules)
- Second baccalaureate degree requirements (127 + 30 additional credits; distinct major required)
- Paired major restrictions (cannot minor in either discipline; cannot declare as double major)

---

════════════════════════════════════════════════════════
SECTION 8 — KNOWN GAPS
════════════════════════════════════════════════════════

List every topic a student might reasonably ask that CANNOT be answered
from the provided documents. Be honest. This section drives the system's
fallback responses — an unanswered question is far better than a
hallucinated answer.

For each gap:

- **Topic:** [what the student might ask]
- **Reason for gap:** [not in any provided document | likely in general docs | may require advisor]
- **Recommended fallback:** [e.g., "Direct student to academic advisor",
  "Direct student to registrar's office", "Check /general document set"]

---

════════════════════════════════════════════════════════
SECTION 9 — ROUTING DECISION GUIDE
════════════════════════════════════════════════════════

This section is written FOR the routing model, not for humans. It provides
explicit decision logic the routing model should follow for this major.

**Default document for broad major questions:** `[filename.txt]`

**When to retrieve multiple documents:**
[list specific conditions — e.g., "Any question about course substitution
requires both `requirements.txt` and `policies.txt`"]

**Degree path disambiguation triggers:**
[list phrases or patterns in student queries that signal the routing model
must ask a clarifying question before retrieving — e.g., "If student says
'the CS degree' without specifying B.S. or B.A., ask which they mean before
routing"]

**High-confidence single-document retrievals:**
[list topics that definitively map to exactly one document]

**Always escalate to human advisor:**
[list any question types that should never be answered by the AI alone —
e.g., exceptions to policy, academic appeals, financial decisions]

**Always retrieve `SU_General_Policies.txt` alongside major docs when:**
- Any graduation eligibility or credit count question
- Any Paideia / general education requirement question
- Any grading policy question (Pass/D/F, grade appeals, incomplete grades)
- Any academic standing question (probation, dismissal, appeal)
- Any transfer credit or credit-by-examination question
- Any disability accommodation question
- Any honors or distinction question (Latin Praise, Departmental Honors, Paideia with Distinction)

**Always retrieve `SU_Resources_and_Financial.txt` alongside major docs when:**
- Any study abroad program question (deadlines, eligibility, credit transfer)
- Any financial aid or tuition question
- Any refund or withdrawal-and-money question
- Any internship funding question (SURF, King Creativity Fund, funded internships)
- Any health professions experience question (St. David's, Houston Methodist)

---

End of skills_index.md. Do not include any text after Section 9.
```

---

## Post-Generation Validation Checklist

After the model returns the skills index, verify the following before
saving the file to the file system. This takes 10-15 minutes and
prevents silent routing failures downstream.

### Document Registry
- [ ] Every `.txt` file in `/docs/extracted/` appears exactly once in Section 2
- [ ] No filename is misspelled or has wrong extension
- [ ] Every description names specific courses, credit hours, or policies
      (reject any description that could apply to any university document)
- [ ] `retrieval_triggers` read like student questions, not catalog entries

### Degree Path Summaries
- [ ] Total credit hours match the source document exactly
- [ ] Every required course is listed with correct course number and credit hours
- [ ] B.S. vs B.A. differences section is present and explicit
- [ ] GPA requirements are captured (both overall and major GPA if different)

### Course Index
- [ ] Spot-check 5 random courses: verify prerequisites against source `.txt`
- [ ] No course listed as having "None" prerequisites when the source shows otherwise
- [ ] All courses required for graduation appear in the index

### Topic Index
- [ ] Count entries — should be 50 minimum, 80 preferred
- [ ] Every required course appears as its own topic entry by course number
- [ ] Transfer credit, substitution, and waiver policies are present

### Query Pattern Map
- [ ] At least 3 questions require both major and /general documents
- [ ] At least one question per student profile listed in the prompt
- [ ] At least 5 course-specific questions present

### Known Gaps
- [ ] Honest — does not omit gaps because they are embarrassing
- [ ] Every gap has a specific recommended fallback action

---

## Re-ingestion Trigger Conditions

Re-run ingestion (and regenerate the skills index) when any of the
following occur:

- A new academic catalog year is published
- Any degree requirements change
- New courses are added or removed from the major
- A prerequisite chain changes
- University-wide policies referenced in major documents are updated
- A new document is added to `/docs/raw/`
- Manual review identifies errors in the existing skills index

After re-ingestion, commit the updated `skills_index.md` to version
control and diff against the previous version to verify changes are
accurate and complete.

---

## Notes on Southwestern University Context

- SU is a small liberal arts university — degree plans may emphasize
  interdisciplinary requirements more than large research universities
- The university uses a semester system
- Catalog year is critical context — always confirm which catalog year
  the documents belong to and note it in the metadata block
- SU's CS department offers B.S., B.A., and Minor — all three paths
  must be captured even if they share a single source document
- Course numbering convention: confirm the prefix (CSCI, CS, etc.)
  from the actual documents — do not assume
- Small department means some courses may have irregular offering
  schedules (every other year, etc.) — capture this if present