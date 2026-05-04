# university-knowledge-assistant

An AI-powered academic advising chatbot for Southwestern University. 

It answers student questions by pulling from a structured knowledge base derived from department PDFs, parses uploaded transcripts to build student profiles, and streams answers through a web interface.

---

## What It Does

- Routes student questions to the right department, then retrieves relevant context before answering
- Parses transcript images to extract course history and populate a student's profile
- Authenticates users via Google OAuth and persists chat history
- Streams responses token by token so users aren't staring at a blank screen
- Fails gracefully. If routing or retrieval breaks down, the system falls back to a general answer rather than crashing

---

## Tech Stack

| Layer | Tools |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTMX |
| Transcript Parsing | LandingAI vision API |
| Auth | Google OAuth 2.0 |
| Logging | `logs/queries.jsonl` |
| LLM | Gemini Flash Lite 3.1 |

---

## Project Structure

```
university-knowledge-assistant
├── Backend/          # FastAPI app, auth, chat history, routing
├── pipeline/         # RAG pipeline, router, answer generation
├── knowledge_base/   # Department PDFs and extracted text
├── ingest/           # Scripts for processing PDFs into the knowledge base
├── Frontend/         # HTMX templates and static assets
└── logs/             # Query audit log (queries.jsonl)
└── scripts/          # Utility scripts to connect pipeline and ingest
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/salasemilio1/university-knowledge-assistant.git
cd university-knowledge-assistant
```

### 2. Setup virtual environment

This project uses `uv` as the package manager. [uv](https://docs.astral.sh/uv/getting-started/installation/) must be installed on your machine.

```bash
uv sync  
```
**NOTE** when using `uv run` the virtual environment is activated automatically for that command

### 3. Configure environment variables

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Required variables:

```
GOOGLE_SERVICE_ACCOUNT_JSON=    # Vertex AI service account key
GOOGLE_CLOUD_PROJECT=           # Vertex AI project name
GOOGLE_CLOUD_LOCATION=          # Vertex AI project location
DATABASE_URL=                   # Point to a MySQL Database
VISION_AGENT_API_KEY=           # LandingAI API key
```

### 4. Run the server

```bash
uv run uvicorn Backend.delivery:app --reload
```

The app will be available at `http://localhost:8000`.

---

## Knowledge Base

The `knowledge_base/` folder contains PDFs and extracted text organized by department. If university data changes, new documents need to be processed through the `ingest/` scripts before the pipeline can use them. Additionally, the `skills_index.md` file must be updated to reflect the changes in PDFs. The  `skills_index.md` files are 'trained' on the raw PDFs, and are the only files retrieved to provide responses.

See the **Developer Manual** for full ingestion instructions.

---

## Logs

All queries are logged to `logs/queries.jsonl`. Each entry includes the query, routed department, and response duration. This is useful for debugging and auditing.

---

## Further Reading

- **User Manual** - how to use the chatbot, upload transcripts, and manage your profile
- **Developer Manual** - architecture deep dive, ingestion pipeline, environment setup, and known limitations
