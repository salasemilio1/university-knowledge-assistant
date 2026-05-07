"""
This script serves to manage most things related to user configuration with SQLAlchemy.
"""



from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker, Session
from sqlalchemy import create_engine, select, exists, delete, String, Boolean, JSON, Integer, ForeignKey, UniqueConstraint, DateTime, func, desc
from sqlalchemy.exc import IntegrityError
import json
from datetime import datetime, timezone
from typing import Optional, List, Any
import re
from sqlalchemy.dialects.mysql import insert as mysql_insert

from dotenv import load_dotenv
import os

load_dotenv() # loads environment variables locally. no effect in production as they are injected
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Database URL not properly set.")


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    """
    pass


class User(Base):
    """
    This class represents the user model with all fields.
    It is an ORM model powered by SQLAlchemy.
    """

    __tablename__ = "users"

    # filled in when user created. pulled from Google
    google_id:Mapped[str] = mapped_column(String(200), nullable=False, primary_key=True)
    email:Mapped[str] = mapped_column(String(200), nullable=False)
    first_name:Mapped[str] = mapped_column(String(100), nullable=False)
    last_name:Mapped[str] = mapped_column(String(100), nullable=False)
    is_profile_complete:Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # initial form data. populated when user fills out setup form
    major:Mapped[str | None] = mapped_column(String(200), nullable=True)
    major_degree_type:Mapped[str | None] = mapped_column(String(200), nullable=True)
    second_major:Mapped[str | None] = mapped_column(String(200), nullable=True)
    second_major_degree_type:Mapped[str | None] = mapped_column(String(200), nullable=True)
    minor:Mapped[str | None] = mapped_column(String(200), nullable=True)
    second_minor:Mapped[str | None] = mapped_column(String(200), nullable=True)
    gpa:Mapped[str | None] = mapped_column(String(200), nullable=True)
    advisor_name:Mapped[str | None] = mapped_column(String(200), nullable=True)
    advisor_email:Mapped[str | None] = mapped_column(String(200), nullable=True)
    grad_year:Mapped[str | None] = mapped_column(String(200), nullable=True)
    courses = relationship(
        "Course",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    transfer_credits = relationship(
        "TransferCredit",
        back_populates="user",
        cascade="all, delete-orphan"
    )

class Course(Base):
    __tablename__ = "courses"

    # Auto-incrementing primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to users table
    google_id: Mapped[str] = mapped_column(ForeignKey("users.google_id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50))
    credits: Mapped[str] = mapped_column(String(5))
    grade: Mapped[Optional[str]] = mapped_column(String(5))
    semester: Mapped[Optional[str]] = mapped_column(String(50))
    is_transfer_equivalent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Don't allow same course code multiple times for a user
    __table_args__ = (UniqueConstraint("google_id","code",),)

    # Relationship back to user
    user = relationship("User", back_populates="courses")

class UnmatchedCourse(Base):
    __tablename__ = "unmatched_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    google_id: Mapped[str] = mapped_column(ForeignKey("users.google_id"), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending") # pending, approved, rejected
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationship back to user
    user = relationship("User")

class TransferCredit(Base):
    __tablename__ = "transfer_credits"

    # Auto-incrementing primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to users table
    google_id: Mapped[str] = mapped_column(ForeignKey("users.google_id"), nullable=False, index=True)

    semester: Mapped[Optional[str]] = mapped_column(String(50))
    institution: Mapped[Optional[str]] = mapped_column(String(50))
    credits: Mapped[Optional[str]] = mapped_column(String(5))

    # Don't allow separate record for same institution in same semester
    __table_args__ = (UniqueConstraint("google_id","institution","semester",),)

    # Relationship back to user
    user = relationship("User", back_populates="transfer_credits")

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    google_id: Mapped[str] = mapped_column(ForeignKey("users.google_id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False) # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(String(4000), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationship back to user
    user = relationship("User")



# create engine and session to interact with DB
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)

Base.metadata.create_all(bind=engine) # create tables for each ORM model if they don't already exist


# API - methods to interact with DB

def get_user_by_id(google_id:str) -> User:
    """
    Retrieves a user by key.

    Args:
        google_id(str): The key to match the user with.
    Returns:
        User | None: User if one exists that matches the key, None otherwise.
    """
    with SessionLocal() as session:
        return session.query(User).filter(User.google_id == google_id).first()

def does_user_exist(google_id:str) -> bool:
    """
    Checks if user exists in DB for given key.

    Args:
        google_id(str): The key to check for.
    Returns:
        bool: True if exists, false otherwise.
    """

    with SessionLocal() as session:
        stmt = select(exists().where(User.google_id == google_id))
        return session.scalar(stmt)


def create_user(google_id:str, email:str, first_name:str, last_name:str) -> bool:
    """
    Creates user if one doesn't exist for the given key.

    Args:
        google_id(str): The Google ID of the account to create a user for.
        email(str): The email of the account to create a user for.
        first_name(str): The first name of the account to create a user for.
        last_name(str): The last name of the account to create a user for.
    Returns:
        bool: True if successful, false if one already exists with the given key.
    """

    if does_user_exist(google_id):
        return False
    
    with SessionLocal() as session:
        user = User(google_id=google_id, email=email, first_name=first_name, last_name=last_name)
        session.add(user)
        session.commit()
        session.refresh(user)
    return True

def update_user(google_id:str, user_data:dict) -> bool:
    """
    Updates a user from profile setup form data.

    Args:
        google_id(str): The Google ID of the account to create a user for.
        user_data(dict): The data to update with.
    Returns:
        bool: True if successful, false if an account doesn't exist.
    """
    if not does_user_exist(google_id):
        return False
    
    with SessionLocal() as session:

        user = session.get(User, google_id)

        for key, value in user_data.items():
            setattr(user, key, value)
        setattr(user, "is_profile_complete", True)

        session.commit()
        session.refresh(user)

    return True
    
def get_user_info(google_id:str):
    """Returns a specific user's info.

    Args:
        google_id(str): The Google ID of the user.
    Returns:
        User | None: User if one with the given key exists, None otherwise.
    """

    user = get_user_by_id(google_id)

    if not user:
        return None
    
    return {
        "name": user.first_name + " " + user.last_name,
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
    }

def get_formatted_user_info(google_id: str):
    """Returns a specific user's info
    which is formatted to make it easily readable by an LLM.

    Args:
        google_id(str): The Google ID of the user.
    Returns:
        str: Formatted user info.
    """
    user_info = get_user_info(google_id)
    if not user_info:
        return "No profile information available."

    su_courses = get_user_courses(google_id)
    transfer_credits = get_user_transfer_credits(google_id)

    second_major_text = ""
    if user_info.get("second_major"):
        second_major_text = f"""\nSecond Major: {user_info["second_major"]} ({user_info["second_major_degree_type"]})"""

    minor_text = ""
    if user_info.get("minor"):
        minor_text = f"""\nMinor: {user_info["minor"]}"""

    second_minor_text = ""
    if user_info.get("second_minor"):
        second_minor_text = f"""\nSecond Minor: {user_info["second_minor"]}"""


    # Format courses as a bulleted list for the LLM
    courses_lines = []
    for c in su_courses:
        courses_lines.append(f"- {(c['semester'] + ': ') if c['semester'] != 'NA' else ''}{c['code']} {c['name']} ({c['credits']} credits, Grade: {c['grade']})")
    courses_text = "\n".join(courses_lines) if courses_lines else "None recorded."

    # Format transfer credits as a bulleted list
    transfer_lines = []
    for t in transfer_credits:
        transfer_lines.append(f"- {t['semester']}: {t['institution']} ({t['credits']} credits)")
    transfer_text = "\n".join(transfer_lines) if transfer_lines else "None recorded."

    return f"""\
Name: {user_info["name"]}
Major: {user_info["major"]} ({user_info["major_degree_type"]}){second_major_text}{minor_text}{second_minor_text}
GPA: {user_info["gpa"]}
Advisor Name: {user_info["advisor_name"]}
Advisor Email: {user_info["advisor_email"]}
Graduation Year: {user_info["grad_year"]}

=== ACADEMIC RECORD ===
COURSES TAKEN:
{courses_text}

TRANSFER CREDITS:
{transfer_text}
=== END ACADEMIC RECORD ===
"""

def normalize_code(code: str) -> str:
    """Normalizes a course code by removing spaces and dashes, and upper-casing."""
    if not code:
        return ""
    return re.sub(r'[\s\-]', '', code).upper()

def get_user_courses(google_id: str):
    """
    Returns a specific user's courses taken (pulled from transcript)
    in a list with a dictionary for each course 

    Args:
        google_id: The Google ID of the user.
    Returns:
        List[Dict[str,Any]]: Course information for each course the user has taken.
    """
    with SessionLocal() as session:
        # Group by code is natively handled by the DB UNIQUE constraint, 
        # but we explicitly deduplicate just in case any legacy data sneaks through
        courses = (
            session.query(Course)
            .filter(Course.google_id == google_id)
            .group_by(Course.code)
            .all()
        )

        return [
            {
                "name": course.name,
                "code": normalize_code(course.code),
                "credits": course.credits,
                "grade": course.grade,
                "semester": course.semester,
                "is_transfer_equivalent": course.is_transfer_equivalent
            }
            for course in courses
        ]
    

def add_courses(google_id:str, courses:List[dict[str,Any]], is_from_transcript=False) -> bool:
    """
    Adds courses from JSON to the courses table.

    Args:
        google_id(str): The Google ID of the account to add courses for.
        courses(List[dict[str,Any]]): List of courses in JSON format.
        is_from_transcript(bool): Whether the data comes from a transcript upload.
    Returns:
        bool: True if successful

    Source-of-truth policy
    ─────────────────────
    • Transcript (is_from_transcript=True):
        – Writes name, credits, semester, and grade on INSERT.
        – On DUPLICATE: updates name, credits, semester, and grade.
          A subsequent manual save will overwrite grade if the user edits it.
    • Manual / frontend (is_from_transcript=False):
        – Writes name, credits, and grade on INSERT (semester stays "NA").
        – On DUPLICATE: always overwrites name, credits, AND grade.
          This is intentional: the user's manual input is always the final
          source of truth and MUST win over any previously transcript-parsed
          grade. Semester is preserved from the original transcript row.
    """

    with SessionLocal() as session:
        if not is_from_transcript:
            # Safely handle user deletions: only delete "NA-semester" courses
            # that are MISSING from the submitted list (i.e. user unchecked them).
            submitted_codes = {normalize_code(c["code"]) for c in courses}
            db_courses = session.query(Course).filter(Course.google_id == google_id, Course.semester == "NA").all()
            for db_c in db_courses:
                if normalize_code(db_c.code) not in submitted_codes:
                    session.delete(db_c)
            session.flush()
            
        for c in courses:
            norm_code = normalize_code(c["code"])
            stmt = mysql_insert(Course).values(
                google_id=google_id,
                name=c["name"],
                code=norm_code,
                credits=str(c["credits"]),
                grade=c.get("grade", "NA"),
                semester=c.get("semester", "NA"),
                is_transfer_equivalent=c.get("is_transfer_equivalent", False)
            )
            
            if is_from_transcript:
                # Transcript sets all fields on conflict.
                # A subsequent manual save will overwrite grade if the user edits it.
                on_duplicate = stmt.on_duplicate_key_update(
                    name=stmt.inserted.name,
                    credits=stmt.inserted.credits,
                    semester=stmt.inserted.semester,
                    grade=stmt.inserted.grade,
                    is_transfer_equivalent=False
                )
            else:
                # Manual input is ALWAYS the source of truth for grade and transfer equivalent flag.
                # Overwrite grade even if the row was previously inserted by a transcript.
                # Do NOT overwrite semester — keep the transcript-provided semester intact.
                on_duplicate = stmt.on_duplicate_key_update(
                    name=stmt.inserted.name,
                    credits=stmt.inserted.credits,
                    grade=stmt.inserted.grade,
                    is_transfer_equivalent=stmt.inserted.is_transfer_equivalent
                )
            
            session.execute(on_duplicate)
            
        session.commit()
    return True

def add_unmatched_courses(google_id: str, raw_texts: List[str]):
    """Stores unrecognized courses for review."""
    with SessionLocal() as session:
        for txt in raw_texts:
            uc = UnmatchedCourse(google_id=google_id, raw_text=txt)
            session.add(uc)
        session.commit()
    return True

def add_transfer_credits(google_id:str, transfer_credits:List[dict[str,Any]]) -> bool:
    """
    Adds transfer credits from JSON to the courses table.

    Args:
        google_id(str): The Google ID of the account to add transfer credits for.
        transfer_credits(List[dict[str,Any]]): List of transfer credits in JSON format.
    Returns:
        bool: True if successful
    """

    with SessionLocal() as session:
        for t in transfer_credits:
            # Check if a record for the same institution and semester already exists
            stmt = select(exists().where(TransferCredit.google_id == google_id, TransferCredit.institution == t["institution"], TransferCredit.semester == t["semester"]))
            if not session.scalar(stmt):
                transfer_credit = TransferCredit(
                    google_id=google_id,
                    semester=t["semester"],
                    institution=t["institution"],
                    # Explicitly cast credits to string for DB compatibility.
                    credits=str(t["credits"])
                )
                try:
                    session.add(transfer_credit)
                    session.commit()
                    session.refresh(transfer_credit)
                except IntegrityError:
                    session.rollback()
    return True

def get_user_transfer_credits(google_id: str):
    """
    Returns a specific user's transfer credits (pulled from transcript)
    in a list with a dictionary for each semester/institution transfer credits were earned.

    Args:
        google_id: The Google ID of the user.
    Returns:
        List[Dict[str,Any]]: Transfer credits earned by semester/institution.
    """
    with SessionLocal() as session:
        transfer_credits = (
            session.query(TransferCredit)
            .filter(TransferCredit.google_id == google_id)
            .all()
        )

        return [
            {
                "semester": transfer_credit.semester,
                "institution": transfer_credit.institution,
                "credits": transfer_credit.credits
            }
            for transfer_credit in transfer_credits
        ]

def add_transcript_info(google_id: str, transcript: dict, is_from_transcript: bool = False):
    """
    Adds transcript information including courses
    and transfer credits from a JSON-derived dictionary.

    Args:
        google_id(str): The Google ID of the account to add transcript information for.
        transcript(dict): Dictionary containing 'courses' and 'transfer_credits'.
        is_from_transcript(bool): Whether the data comes from a transcript (affects course cleanup).
    """
    courses = transcript.get("courses", [])
    transfer_credits = transcript.get("transfer_credits", [])

    add_courses(google_id, courses, is_from_transcript=is_from_transcript)
    add_transfer_credits(google_id, transfer_credits)
def add_chat_message(google_id: str, role: str, content: str):
    """
    Persists a chat message to the history and trims to the last 10 messages.
    Uses a single transaction to ensure atomicity.

    Args:
        google_id: User's Google ID.
        role: 'user' or 'assistant'.
        content: The message text.
    """
    with SessionLocal() as session:
        with session.begin():
            # 1. Add new message
            message = ChatHistory(google_id=google_id, role=role, content=content)
            session.add(message)
            session.flush() # Ensure ID and timestamp exist for the trim subquery

            # 2. Trim history: keep only most recent 10 messages for this user
            ids = (
                session.query(ChatHistory.id)
                .filter(ChatHistory.google_id == google_id)
                .order_by(desc(ChatHistory.timestamp), desc(ChatHistory.id))
                .all()
            )
            if len(ids) > 10:
                to_delete = [r.id for r in ids[10:]]
                session.query(ChatHistory).filter(ChatHistory.id.in_(to_delete)).delete(synchronize_session=False)

def get_chat_history(google_id: str, limit: int = 10) -> List[dict]:
    """
    Retrieves the last N messages for a user.

    Args:
        google_id: User's Google ID.
        limit: Number of messages to retrieve.
    Returns:
        List[dict]: [{'role': ..., 'content': ...}, ...] in chronological order.
    """
    with SessionLocal() as session:
        messages = (
            session.query(ChatHistory)
            .filter(ChatHistory.google_id == google_id)
            .order_by(desc(ChatHistory.timestamp), desc(ChatHistory.id))
            .limit(limit)
            .all()
        )
        # Reverse to get chronological order
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]
