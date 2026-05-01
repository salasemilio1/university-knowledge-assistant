import json
import signal
from pathlib import Path

from pipeline.answerer import load_context
from pipeline.gemini_client import generate, extract_json
from pipeline.router import load_registry

BASE_PATH = "knowledge_base"
OUTPUT_PATH = Path("knowledge_base/degree_requirements.json")
TIMEOUT_SECONDS = 200


def timeout_handler(signum, frame):
    raise TimeoutError("LLM call timed out")


signal.signal(signal.SIGALRM, timeout_handler)


def prompt_for_department(department_name, context):
    return f"""
Extract all major and minor degree requirements from the source text.

Department: {department_name}

Return ONLY valid JSON in this shape:

{{
  "majors": {{
    "Major Name": {{
      "BA": {{
        "requiredCredits": <total credits required for this degree>,
        "requiredCourses": [
          {{ "code": "ABC12-345", "name": "Course Name", "credits": <number> }}
        ],
        "electiveGroups": [
          {{
            "name": "Elective group name",
            "coursesRequired": <number of courses required>,
            "creditsRequired": <number of credits required>,
            "options": [
              {{ "code": "ABC12-345", "name": "Course Name", "credits": <number> }}
            ]
          }}
        ],
        "notes": []
      }}
    }}
  }},
  "minors": {{
    "Minor Name": {{
      "requiredCredits": <total credits required>,
      "requiredCourses": [],
      "electiveGroups": [],
      "notes": []
    }}
  }}
}}

Rules:
- Use ONLY the provided source text.
- Do NOT invent courses or requirements.
- Put exact must-take courses in requiredCourses.
- Put choice-based requirements like "choose 2 from..." or "two approved upper-level electives" in electiveGroups.
- Do NOT put every elective option in requiredCourses.
- If course credits are not explicitly stated, assume 4.
- If total required credits are not explicitly stated, calculate them from requiredCourses plus electiveGroups creditsRequired.
- If a requirement is too vague to structure, put it in notes.
- If a degree type does not exist, omit it.
- Return JSON only. No markdown.

SOURCE TEXT:
{context}
"""


def main():
    registry = load_registry(BASE_PATH)

    if OUTPUT_PATH.exists():
        all_requirements = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    else:
        all_requirements = {}

    for slug, meta in registry.items():
        department_name = meta.get("name", slug)

        if slug in all_requirements:
          print(f"Skipping {department_name} — already processed.")
          continue
        
        print(f"\n--- Processing {department_name} ({slug}) ---")

        try:
            context = load_context(
                departments=[slug],
                base_path=BASE_PATH
            )

            print(f"Context length: {len(context)} characters")

            prompt = prompt_for_department(department_name, context)

            print("Calling LLM...")
            signal.alarm(TIMEOUT_SECONDS)
            raw = generate(prompt)
            signal.alarm(0)
            print("LLM returned.")

            cleaned = extract_json(raw)
            data = json.loads(cleaned)

            all_requirements[slug] = data

            OUTPUT_PATH.write_text(
                json.dumps(all_requirements, indent=2),
                encoding="utf-8"
            )

            print(f"Saved {department_name}.")

        except TimeoutError:
            signal.alarm(0)
            print(f"Timed out on {department_name}. Skipping.")
            continue

        except json.JSONDecodeError:
            signal.alarm(0)
            print(f"Failed to parse JSON for {department_name}. Skipping.")
            continue

        except Exception as exc:
            signal.alarm(0)
            print(f"Error processing {department_name}: {exc}")
            continue

    print(f"\nDone. Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()