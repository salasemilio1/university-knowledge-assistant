"""
delivery.py — the web entry point for the advising assistant.

This file does three things:
  1. Serves the frontend HTML page when a user visits the site.
  2. Receives a student's question from the frontend form.
  3. Runs the question through the pipeline and returns the answer.

All business logic lives in the pipeline/ folder.
This file is only responsible for HTTP in / HTTP out.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
import os
from dotenv import load_dotenv

from fastapi import FastAPI, Form, Request, Response, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

import shutil

from google.oauth2 import id_token
from google.auth.transport import requests

from pipeline.router import route
from pipeline.answerer import answer, stream_answer

from Backend.user_db import create_user, update_user, get_user_by_id, get_user_courses, get_user_transfer_credits, add_courses, add_transcript_info

# ── Setup ─────────────────────────────────────────────────────────────────────

# Google OAuth client
CLIENT_ID = "645267348660-8l6o31mokh4d7g4a0h57suu2lf36motg.apps.googleusercontent.com"

load_dotenv() # Load environment variables
# Used for session middleware
SECRET_KEY = os.getenv("SECRET_KEY")

# Build absolute paths so the server works regardless of where it's launched from
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_PATH = str(_PROJECT_ROOT / "knowledge_base")
FRONTEND_DIR = _PROJECT_ROOT / "Frontend"
LOG_DIR = _PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "queries.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI()

# Serve all files inside Frontend/ as static assets (CSS, JS, images, etc.)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/kb", StaticFiles(directory="knowledge_base"), name="kb")

# Add middleware (used for user sessions)
app.add_middleware(SessionMiddleware, SECRET_KEY)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
@app.get("/chat", response_class=FileResponse)
def index(request: Request):
    """Serve the main chat page."""
    if(request.session.get("user_id")):
        return FileResponse(FRONTEND_DIR / "index.html")
    else:
        # Route to sign-in page if user is not signed in
        return RedirectResponse(url="/sign-in", status_code=302)

@app.get("/sign-in", response_class=FileResponse)
def sign_in(request: Request):
    """Serve the sign-in page."""
    if(request.session.get("user_id")):
        return RedirectResponse(url="/", status_code = 302)
    else:
        return FileResponse(FRONTEND_DIR / "sign_in_page.html")

@app.post("/auth/google")
async def google_auth(request: Request, response: Response, token: str = Form(...)):
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            CLIENT_ID
        )
        
        google_id= idinfo.get("sub")
        email = idinfo.get("email")

        name = idinfo.get("name")
        first_name, last_name = name.split(" ", 1)

        # Add user to database, if not already in the database
        create_user(google_id,email,first_name,last_name)

        # Create user session
        request.session["user_id"] = google_id

        # Redirect user to main page after login
        response.headers["HX-Redirect"] = "/"
    
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")
    

@app.get("/courses")
async def get_courses():
    """Returns the full list of courses as objects."""
    courses_file = _PROJECT_ROOT / "knowledge_base" / "courses.json"
    if not courses_file.exists():
        return []
    
    with open(courses_file, "r") as f:
        courses_dict = json.load(f)
    
    # Convert dict {code: title} to list [{code, title}]
    return [{"code": code, "title": title} for code, title in courses_dict.items()]

@app.get("/api/departments")
def get_departments():
    departments_file = _PROJECT_ROOT / "knowledge_base" / "departments.json"
    if not departments_file.exists():
        return []
    
    with open(departments_file, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


@app.get("/profile")
async def profile(request:Request):
    google_id = request.session.get("user_id")
    if not google_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_user_by_id(google_id)
    courses = get_user_courses(google_id)
    transfer = get_user_transfer_credits(google_id)

    return {
        "name": user.first_name + " " + user.last_name,
        "email": user.email,
        "is_profile_complete": user.is_profile_complete,
        "major": user.major,
        "major_degree_type": user.major_degree_type,
        "second_major": user.second_major,
        "second_major_degree_type": user.second_major_degree_type,
        "minor": user.minor,
        "second_minor": user.second_minor,
        "gpa": user.gpa,
        "advisor_name": user.advisor_name,
        "advisor_email": user.advisor_email,
        "grad_year": user.grad_year,
        "courses": courses,
        "transfer_credits": transfer
    }

@app.post("/sign-out")
def sign_out(request: Request, response: Response):
    request.session.clear()

    # Reroute to sign-in page after user session is cleared
    response.headers["HX-Redirect"] = "/sign-in"

@app.post("/users")
async def users(request:Request):

# TODO
#   validate input

    form = await request.form() # get form data. Form object is accessible like a dictionary

    # expected form fields from frontend
    expected_field_names = [
    "major",
    "major_degree_type",
    "second_major",
    "second_major_degree_type",
    "minor",
    "second_minor",
    "gpa",
    "gpa_custom",
    "advisor_name",
    "advisor_email",
    "courses", # From user profile
    "courses_custom",
    "grad_year",
    "grad_year_custom"
    ]

    form_data = {} # form data

    # retrieve form data
    for field in expected_field_names:
        if field == "courses":
            form_data[field] = form.getlist(field)
        else:
            form_data[field] = form.get(field)

    # TODO validate that all fields are present and are the correct type and specifications for DB (string length, etc)

    user_data = {} # user data to update requesting (currently authorized) user with

    # populate final values to update user with.
    user_data["major"] = form_data["major"]
    user_data["major_degree_type"] = form_data["major_degree_type"]
    user_data["second_major"] = form_data["second_major"]
    user_data["second_major_degree_type"] = form_data["second_major_degree_type"]
    user_data["minor"] = form_data["minor"]
    user_data["second_minor"] = form_data["second_minor"]
    user_data["gpa"] = form_data["gpa_custom"] if form_data["gpa"] == "custom" else form_data["gpa"]
    user_data["advisor_name"] = form_data["advisor_name"]
    user_data["advisor_email"] = form_data["advisor_email"]
    user_data["grad_year"] = form_data["grad_year_custom"] if form_data["grad_year"] == "custom" else form_data["grad_year"]
    
    courses_list = list(form_data["courses"]) # get courses listed in checkbox
    courses = []
    # Get course list into list of dictionaries
    for c in courses_list:
        code, name = c.split(" ", 1)
        course = {}
        course["name"] = name
        course["code"] = code
        course["credits"] = code[-1] # Last digit of course code indicates credits
        course["semester"] = "NA"
        course["grade"] = "NA"
        courses.append(course)

    # retrieve currently authed user
    google_id = request.session.get("user_id")
    if not google_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    
    update_user(google_id, user_data)
    add_courses(google_id,courses)


    return HTMLResponse("<div style='color:#808080;'>Profile saved.</div>")

@app.post("/api/transcript/upload")
async def upload_transcript(request: Request, file: UploadFile = File(...)):
    """
    Handles a single cropped transcript page image upload, processes it using
    LandingAI's extraction, and stores the results.
    """
    google_id = request.session.get("user_id")
    if not google_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    
    # 1. Validate file
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    try:
        import tempfile
        import time
        import shutil

        timestamp = int(time.time())
        debug_save = os.environ.get("DEBUG_SAVE_EXTRACTIONS", "").lower() == "true"

        # 2. Instantiate LandingAIADE
        if not os.environ.get("VISION_AGENT_API_KEY"):
            from dotenv import load_dotenv
            load_dotenv(override=True)
            if not os.environ.get("VISION_AGENT_API_KEY"):
                raise Exception("VISION_AGENT_API_KEY is not set.")
            
        from landingai_ade import LandingAIADE
        client = LandingAIADE()
        
        # 3. Load schema
        schema_path = _PROJECT_ROOT / "knowledge_base" / "schema-v1.json"
        if not schema_path.exists():
            raise Exception("Schema file not found.")
            
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_data = json.load(f)

        # Use tempfile.TemporaryDirectory to ensure automatic cleanup of temp files
        with tempfile.TemporaryDirectory() as tmpdirname:
            temp_img_path = Path(tmpdirname) / f"temp_{google_id}_{timestamp}.jpg"
            
            # Save temp image
            with open(temp_img_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            # 4. Parse document
            parse_response = await run_in_threadpool(
                client.parse,
                document=str(temp_img_path),
                model="dpt-2-mini"
            )
            
            # Save markdown to temp file for extract method
            temp_md_path = Path(tmpdirname) / f"temp_{google_id}_{timestamp}.md"
            with open(temp_md_path, "w", encoding="utf-8") as f:
                f.write(parse_response.markdown)
                
            # 5. Extract using schema
            extract_response = await run_in_threadpool(
                client.extract,
                markdown=str(temp_md_path),
                schema=json.dumps(schema_data),
                model="extract-20260314"
            )
            extracted = extract_response.extraction
            
            # If debug mode is enabled, save everything to extraction_results/
            if debug_save:
                extraction_dir = _PROJECT_ROOT / "extraction_results"
                extraction_dir.mkdir(exist_ok=True)
                shutil.copy(temp_img_path, extraction_dir)
                shutil.copy(temp_md_path, extraction_dir)
                result_path = extraction_dir / f"result_{google_id}_{timestamp}.json"
                with open(result_path, "w", encoding="utf-8") as f:
                    json.dump(extracted, f, indent=2)
                    
        # Verification Step: Assert keys match schema top-level keys
        # The schema uses "properties" for its top-level fields
        schema_keys = set(schema_data.get("properties", {}).keys())
        extracted_keys = set(extracted.keys())
        missing_keys = schema_keys - extracted_keys
        extra_keys = extracted_keys - schema_keys
        if missing_keys or extra_keys:
            logging.warning(f"Extraction mismatch for user {google_id}: Missing {missing_keys}, Extra {extra_keys}")

        # 7. Store in Database
        db_success = False
        try:
            # add_transcript_info is synchronous, so we run it in a threadpool
            await run_in_threadpool(add_transcript_info, google_id, extracted, is_from_transcript=True)
            db_success = True
        except Exception as db_exc:
            logging.error("Database storage failed for user %s: %s", google_id, db_exc)

        if not db_success:
            return HTMLResponse(
                content="<div style='color: #FFA500;'>Transcript processed successfully, but database update failed.</div>",
                status_code=200
            )

        return HTMLResponse(
            content="<div style='color: #4CAF50;'>Transcript upload complete!</div>", 
            status_code=200,
            headers={"HX-Trigger": "transcriptUploaded"}
        )

    except Exception as exc:
        logging.error("Transcript processing failed: %s", exc)
        return HTMLResponse(
            content=f"<div style='color: #F44336;'>Processing failed: {str(exc)}</div>",
            status_code=500
        )

@app.post("/ask", response_class=HTMLResponse)
async def ask(request: Request, query: str = Form(...)):
    """
    Receive the student's question, run the pipeline, return an HTML snippet.

    The frontend sends: POST /ask with form field 'query'.
    HTMX swaps the returned HTML into the response area on the page.

    Steps:
      1. Route — decide which department folders to look in.
      2. Retrieve — pick which documents to load.
      3. Answer — generate the final response from those documents.

    If anything goes wrong at any step, return an error message instead
    of crashing, so the user always gets some feedback.
    """
    query = query.strip()

    if not query:
        return _error_html("Please enter a question before submitting.")

    start_time = time.time()

    # Get google id so the router can get user profile
    google_id = request.session.get("user_id")

    # Step 1 — Route to the right department(s) and classify complexity
    try:
        route_result = route(query, KNOWLEDGE_BASE_PATH, google_id)
        logging.info("Complexity for query '%s': %s", query[:50], route_result.complexity)
    except Exception as exc:
        logging.error("Routing failed: %s", exc)
        return _error_html("Something went wrong while routing your question. Please try again.")

    # Step 2 — Generate the answer
    # Note: history is not passed here (stateless for now).
    # To add conversation memory later, store history in a session or pass it from the client.
    try:
        answer_text = answer(
            question=query,
            departments=route_result.departments,
            complexity=route_result.complexity,
            base_path=KNOWLEDGE_BASE_PATH,
            history=[],
            google_id=google_id
        )
    except Exception as exc:
        logging.error("Answer generation failed: %s", exc)
        return _error_html("Something went wrong while generating your answer. Please try again.")

    # Log the query for review
    _log_query(
        question=query,
        routed_majors=route_result.departments,
        selected_docs=[f"{route_result.complexity} context"],
        answer_text=answer_text,
        duration_seconds=time.time() - start_time,
    )

    return _answer_html(query, answer_text)


@app.post("/ask/stream")
async def ask_stream(request: Request, query: str = Form(...)):
    """
    Streaming variant of /ask.

    Steps 1 (route) and 2 (retrieve) run synchronously — identical to /ask.
    Step 3 (answer) streams tokens to the browser via StreamingResponse so
    the user sees text as it is generated rather than waiting for completion.
    The frontend reads the plain-text stream and renders Markdown once done.
    """
    query = query.strip()
    if not query:
        return Response(content="Please enter a question.", status_code=400)

    google_id = request.session.get("user_id")
    start_time = time.time()

    try:
        route_result = route(query, KNOWLEDGE_BASE_PATH, google_id)
        logging.info("Complexity for query '%s': %s", query[:50], route_result.complexity)
    except Exception as exc:
        logging.error("Routing failed: %s", exc)
        return Response(content="Routing error.", status_code=500)

    async def token_generator():
        """Drive the blocking stream_answer generator inside a thread pool."""
        full_chunks: list[str] = []
        sentinel = object()
        gen = stream_answer(
            question=query,
            departments=route_result.departments,
            complexity=route_result.complexity,
            base_path=KNOWLEDGE_BASE_PATH,
            history=[],
            google_id=google_id
        )
        try:
            while True:
                chunk = await run_in_threadpool(next, gen, sentinel)
                if chunk is sentinel:
                    break
                full_chunks.append(chunk)
                yield chunk
        except Exception as exc:
            logging.error("Token streaming failed: %s", exc)
            yield f"\n\n[ERROR] {exc}"
        finally:
            _log_query(
                question=query,
                routed_majors=route_result.departments,
                selected_docs=[f"{route_result.complexity} context"],
                answer_text="".join(full_chunks),
                duration_seconds=time.time() - start_time,
            )

    return StreamingResponse(token_generator(), media_type="text/plain")


# ── HTML snippet builders ──────────────────────────────────────────────────────
#
# These functions return small HTML strings that HTMX swaps into the page.
# Keeping them here (instead of Jinja2 templates) is fine for a response
# this simple. If the snippets grow larger, move them to templates/.

def _answer_html(question: str, answer_text: str) -> str:
    """Wrap the pipeline answer in a collapsible <details> block.

    The question is the always-visible summary (the clickable header).
    The answer body expands when the user clicks it.
    'open' makes the block start expanded so the answer is immediately readable.
    """
    return f"""
    <div class="response-block">
        <details open>
            <summary>{question}</summary>
            <div class="response-answer">{answer_text}</div>
        </details>
    </div>
    """


def _error_html(message: str) -> str:
    """Wrap an error message in a styled HTML block to display on the page."""
    return f"""
    <div class="response-block response-error">
        <p>{message}</p>
    </div>
    """


# ── Logging ───────────────────────────────────────────────────────────────────

def _log_query(
    question: str,
    routed_majors: list[str],
    selected_docs: list[str],
    answer_text: str,
    duration_seconds: float,
) -> None:
    """Write one query's results to a newline-delimited JSON log file.

    Each line in the log file is one complete JSON object. This format is
    easy to read line-by-line and works well with tools like jq or pandas.
    Logging failures are swallowed so they never crash the server.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "routed_majors": routed_majors,
        "selected_docs": selected_docs,
        "answer": answer_text,
        "duration_seconds": round(duration_seconds, 2),
    }

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logging.warning("Failed to write query log: %s", exc)
