"""
Requires dependency: pip install landingai-ade

====================
Ingests a PDF with LandingAI's Agentic Document Extraction (ADE), saves the
generated Markdown, then runs schema-based extraction using an external JSON
schema file. Results are ready to store as user info in a database.

"""

import os
from dotenv import load_dotenv
import json
from pathlib import Path
from landingai_ade import LandingAIADE

load_dotenv() 

# =============================================================================
# CONFIGURATION — edit these values
# =============================================================================

PDF_PATH      = "scripts/cropped.pdf"   # Path to the PDF you want to process
SCHEMA_PATH   = "scripts/schema-v1.json"         # Path to your JSON schema file
MARKDOWN_PATH = "scripts\landing_ai_output\output.md"           # Where the parsed Markdown will be saved
EXTRACT_OUT   = "scripts\landing_ai_output\extracted_data.json" # Where the final extracted fields will be saved


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def load_schema(schema_path: str) -> dict:
    """Load and validate a JSON schema from a file."""
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    if path.suffix.lower() != ".json":
        raise ValueError(f"Schema file must be a .json file, got: {schema_path}")

    with open(path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    if not isinstance(schema, dict):
        raise ValueError("Schema file must contain a JSON object at the top level.")

    print(f"      Schema loaded from: {schema_path}")
    return schema


def parse_pdf(client: LandingAIADE, pdf_path: str, markdown_path: str) -> None:
    """
    Step 1 & 2: Send the PDF to LandingAI and save the returned Markdown to disk.
    """
    print(f"[1/2] Parsing PDF: {pdf_path}")

    response = client.parse(
        document=Path(pdf_path),
        model="dpt-2-latest",   # LandingAI's latest document parsing model
    )

    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(response.markdown)

    print(f"      Markdown saved to: {markdown_path}")
    print(f"      Pages parsed: {response.metadata.page_count}")
    print(f"      Chunks found: {len(response.chunks)}")


def extract_fields(client: LandingAIADE, markdown_path: str, schema: dict, output_path: str) -> dict:
    """
    Step 3: Run schema-based extraction on the saved Markdown.

    Returns a dict of the extracted fields, ready for database insertion.
    """
    print(f"\n[2/2] Extracting fields from: {markdown_path}")

    response = client.extract(
        markdown=Path(markdown_path),
        schema=json.dumps(schema),
        model="extract-20260314",   # LandingAI's latest extraction model
    )

    extracted = response.extraction

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2)

    print(f"      Extraction saved to: {output_path}")

    return extracted




# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":

    # Validate API key
    if not os.environ.get("VISION_AGENT_API_KEY"):
        raise EnvironmentError(
            "VISION_AGENT_API_KEY is not set.\n"
            "Run: export VISION_AGENT_API_KEY=your_key_here"
        )

    client = LandingAIADE()

    # Load the JSON schema from file
    schema = load_schema(SCHEMA_PATH)

    # schema = "schema-v1.json"
    # Step 1 & 2: Parse the PDF and save its Markdown
    parse_pdf(client, PDF_PATH, MARKDOWN_PATH)

    # Step 3: Extract structured fields from the Markdown using the schema
    extracted_data = extract_fields(client, MARKDOWN_PATH, schema, EXTRACT_OUT)


    # `extracted_data` is a plain dict  pass it straight to your DB layer, e.g.:
    #
    #   db.users.insert_one(extracted_data)                      # MongoDB
    #   cursor.execute("INSERT INTO users ...", extracted_data)  # SQL