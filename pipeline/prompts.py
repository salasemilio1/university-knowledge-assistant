"""
Prompt templates for the three-call pipeline.

Each function returns a fully-formed prompt string. No logic lives here —
only text assembly. This makes prompts easy to read, diff, and iterate on.
"""


def router_prompt(question: str, registry_json: str, profile: str | None = None) -> str:
    """Build the Call 1 prompt: route a question AND classify its complexity.

    The router does two jobs in a single LLM call:
      1. Route — decide which department slug(s) are relevant.
      2. Classify — decide whether the question is simple or complex.

    Complexity drives how much context the answerer receives (Call 2):
      - simple  → skills_index.md only (fast; covers most advising questions)
      - complex → skills_index.md + all .txt files (thorough; for broad or
                  multi-faceted questions)

    When in doubt, return "complex" — it is safer to over-fetch than to
    give an incomplete answer.

    Args:
        question:      The student's question.
        registry_json: Raw JSON string from context_registry.json.
        profile:       Optional formatted student profile string.

    Returns:
        A prompt that instructs the LLM to return exactly this JSON shape:
        {"departments": ["slug_a"], "complexity": "simple"}
    """
    profile_block = ""
    if profile:
        profile_block = f"""\
=== STUDENT PROFILE ===
{profile}
=== END STUDENT PROFILE ===
Use this ONLY to help determine relevant departments.
Do NOT assume the student is restricted to these departments.
"""

    return f"""\
You are a university advising router. Given a student's question, you must:

  1. ROUTE — Identify which department(s) from the registry are relevant.
  2. CLASSIFY — Decide if the question is simple or complex.

=== DEPARTMENT REGISTRY ===
{registry_json}
=== END REGISTRY ===

{profile_block}
STUDENT QUESTION:
{question}

=== COMPLEXITY GUIDE ===
simple  — A focused question answerable from a department's summary index
          (e.g. "does anthropology have a BS?", "who is the CS department chair?",
          "what courses are required for the biology major?").

complex — A broad, multi-part, or cross-cutting question that likely needs the
          full document set to answer accurately
          (e.g. "what are all my graduation options given my completed courses?",
          "how do I plan a 4-year schedule for a CS/Math double major?").

When uncertain, choose complex.
=== END GUIDE ===

INSTRUCTIONS:
- Return ONLY a JSON object — no other text, no markdown.
- "departments" must be a JSON array of slug strings from the registry.
- "complexity" must be exactly "simple" or "complex".

Example: {{"departments": ["computer_science"], "complexity": "simple"}}
"""


def answerer_prompt(
    question: str,
    context: str,
    history: str | None = None,
    profile: str | None = None,
) -> str:
    """Build the Call 3 prompt: generate the final answer from loaded documents.

    Args:
        question: The student's question.
        context:  Concatenated contents of the selected .txt files, each
                  preceded by a source header.
        history:  Optional plaintext block of the last few Q&A pairs.

    Returns:
        A prompt string instructing the LLM to produce a cited answer.
    """
    history_block = ""
    if history:
        history_block = f"""\

=== RECENT CONVERSATION HISTORY ===
{history}
=== END HISTORY ===
Note: Use the conversation history for context if the student's current
question refers to something discussed earlier. Do not repeat previous
answers verbatim.
"""

    profile_block = ""      
    if profile:
      profile_block = f"""\
=== STUDENT PROFILE ===
{profile}
=== END STUDENT PROFILE ===
Use the student profile information to tailor your answer to the student.
- You may use this to make recommendations.
- Do not cite this section as a source.
- If the profile conflicts with source documents, trust the source documents.
"""

    return f"""\
You are an AI academic advisor for Southwestern University. Answer the
student's question using ONLY the source documents provided below.
You may use conversation history and student profile information for context when available.
{history_block}

{profile_block}

=== SOURCE DOCUMENTS ===
{context}
=== END SOURCE DOCUMENTS ===


STUDENT QUESTION:
{question}

INSTRUCTIONS:
- Answer clearly and concisely — students are busy.
- After each claim, cite the source in parentheses, e.g. (Source: Courses.txt).
- If the documents don't contain enough information to fully answer the
  question, say so honestly and direct the student to the appropriate
  office or advisor. Common referrals:
    * GPA / graduation policy → Registrar's office
    * Financial aid → Financial Aid office
    * Disability accommodations → Student Accessibility Services
    * Course substitutions / exceptions → Department Chair (Dr. Anthony,
      anthonyb@southwestern.edu)
- If the question involves choosing between B.A. and B.S. and the student
  hasn't specified which, ask them to clarify.
- Do NOT invent information that is not in the source documents.
- Keep the tone friendly and supportive.
"""
