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

from fastapi import FastAPI, Form, Request, Response, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from starlette.middleware.sessions import SessionMiddleware

from google.oauth2 import id_token
from google.auth.transport import requests

from pipeline.router import route
from pipeline.retriever import retrieve
from pipeline.answerer import answer

from Backend.user_db import create_user, update_user, get_user_by_id

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
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI()

# Serve all files inside Frontend/ as static assets (CSS, JS, images, etc.)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Add middleware (used for user sessions)
app.add_middleware(SessionMiddleware, SECRET_KEY)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
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
    

@app.get("/profile")
async def profile(request:Request):
    google_id = request.session.get("user_id")
    if not google_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_user_by_id(google_id)

    return {
        "name": user.first_name + " " + user.last_name,
        "email": user.email,
        "is_profile_complete": user.is_profile_complete,
        "major": user.major,
        "second_major": user.second_major,
        "minor": user.minor,
        "second_minor": user.second_minor,
        "gpa": user.gpa,
        "advisor_name": user.advisor_name,
        "advisor_email": user.advisor_email,
        "grad_year": user.grad_year,
        "courses": user.courses
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
    "second_major",
    "minor",
    "second_minor",
    "gpa",
    "gpa_custom",
    "advisor_name",
    "advisor_email",
    "courses",
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
    user_data["second_major"] = form_data["second_major"]
    user_data["minor"] = form_data["minor"]
    user_data["second_minor"] = form_data["second_minor"]
    user_data["gpa"] = form_data["gpa_custom"] if form_data["gpa"] == "custom" else form_data["gpa"]
    user_data["advisor_name"] = form_data["advisor_name"]
    user_data["advisor_email"] = form_data["advisor_email"]
    user_data["grad_year"] = form_data["grad_year_custom"] if form_data["grad_year"] == "custom" else form_data["grad_year"]
    
    courses = list(form_data["courses"]) # get courses listed in checkbox

    # get courses listed in custom and extend list
    custom_courses_raw = form_data["courses_custom"]
    if custom_courses_raw:
        custom_courses = [
            course.strip()
            for course in custom_courses_raw.split(",")
            if course.strip()
        ]
        courses.extend(custom_courses)

    # update user data field
    user_data["courses"] = courses if courses else None

    # retrieve currently authed user
    google_id = request.session.get("user_id")
    if not google_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    
    update_user(google_id, user_data)

    return HTMLResponse("<div style='color:#19c37d;'>Profile saved.</div>")

@app.post("/ask", response_class=HTMLResponse)
async def ask(query: str = Form(...)):
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

    # Step 1 — Route to the right department(s)
    try:
        routed_majors = route(query, KNOWLEDGE_BASE_PATH)
    except Exception as exc:
        logging.error("Routing failed: %s", exc)
        return _error_html("Something went wrong while routing your question. Please try again.")

    # Step 2 — Select which documents to load
    try:
        doc_list = retrieve(query, routed_majors, KNOWLEDGE_BASE_PATH)
    except Exception as exc:
        logging.error("Retrieval failed: %s", exc)
        return _error_html("Something went wrong while retrieving documents. Please try again.")

    if not doc_list:
        return _error_html(
            "I couldn't find any relevant documents for that question. "
            "Try rephrasing, or contact your academic advisor directly."
        )

    # Step 3 — Generate the answer
    # Note: history is not passed here (stateless for now).
    # To add conversation memory later, store history in a session or pass it from the client.
    try:
        answer_text = answer(query, doc_list, history=[])
    except Exception as exc:
        logging.error("Answer generation failed: %s", exc)
        return _error_html("Something went wrong while generating your answer. Please try again.")

    # Log the query for review
    _log_query(
        question=query,
        routed_majors=routed_majors,
        selected_docs=[d["filename"] for d in doc_list],
        answer_text=answer_text,
        duration_seconds=time.time() - start_time,
    )

    return _answer_html(query, answer_text)


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
