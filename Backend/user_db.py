"""
This script serves to manage most things related to user configuration with SQLAlchemy.
"""



from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker, Session
from sqlalchemy import create_engine, select, exists, delete, String, Boolean, JSON, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.exc import IntegrityError
import json
from typing import Optional, List, Any

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

    # initial form data. pulled in when user fills out setup form
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

    # Don't allow same course in same semester
    __table_args__ = (UniqueConstraint("google_id","code","semester",),)

    # Relationship back to user
    user = relationship("User", back_populates="courses")

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
        courses = (
            session.query(Course)
            .filter(Course.google_id == google_id)
            .all()
        )

        return [
            {
                "name": course.name,
                "code": course.code,
                "credits": course.credits,
                "grade": course.grade,
                "semester": course.semester
            }
            for course in courses
        ]
    

def add_courses(google_id:str, courses:List[dict[str,Any]], is_from_transcript=False) -> bool:
    """
    Adds courses from JSON to the courses table.

    Args:
        google_id(str): The Google ID of the account to add courses for.
        courses(List[dict[str,Any]]): List of courses in JSON format.
    Returns:
        bool: True if successful
    """

    with SessionLocal() as session:
        if not is_from_transcript:
            stmt = delete(Course).where(Course.semester == "NA")
            session.execute(stmt)
            
        for c in courses:
            # Check if a record for the same course and semester already exists
            stmt = select(exists().where(Course.google_id == google_id, Course.code == c["code"], Course.semester == c["semester"]))
            if not session.scalar(stmt):
                course = Course(
                    google_id=google_id,
                    name=c["name"],
                    code=c["code"],
                    # Explicitly cast credits to string for DB compatibility.
                    credits=str(c["credits"]),
                    grade=c["grade"],
                    semester=c["semester"]
                )
                try:
                    session.add(course)
                except IntegrityError:
                    session.rollback()
                    
        session.commit()
        session.refresh(course)
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

def add_transcript_info(google_id: str, transcript: dict):
    """
    Adds transcript information including courses
    and transfer credits from a JSON-derived dictionary.

    Args:
        google_id(str): The Google ID of the account to add transcript information for.
        transcript(dict): Dictionary containing 'courses' and 'transfer_credits'.
    """
    courses = transcript.get("courses", [])
    transfer_credits = transcript.get("transfer_credits", [])

    add_courses(google_id, courses)
    add_transfer_credits(google_id, transfer_credits)

def main():
    add_courses("105756527656204148979", [{"code": "ABC123", "name": "placeholder", "credits": "4", "grade": "A", "semester": "placeholder"}])
if __name__ == "__main__":
    main()