"""
This script serves to manage most things related to user configuration with SQLAlchemy.
"""


from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker, Session
from sqlalchemy import create_engine, select, exists, String, Boolean, JSON, Integer, ForeignKey
from typing import Optional

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
    courses_json:Mapped[list | None] = mapped_column(JSON, nullable=True)
    courses = relationship(
        "Course",
        back_populates="user",
        cascade="all, delete-orphan"
    )

class Course(Base):
    __tablename__ = "courses"

    # Auto-incrementing primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to users table (assuming users.id is UUID stored as CHAR(36))
    google_id: Mapped[str] = mapped_column(ForeignKey("users.google_id"), nullable=False, index=True)

    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_code: Mapped[str] = mapped_column(String(50))
    grade: Mapped[Optional[str]] = mapped_column(String(5))
    semester: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationship back to user
    user = relationship("User", back_populates="courses")

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
        "second_major": user.second_major,
        "minor": user.minor,
        "second_minor": user.second_minor,
        "gpa": user.gpa,
        "advisor_name": user.advisor_name,
        "advisor_email": user.advisor_email,
        "grad_year": user.grad_year,
        "courses": user.courses,
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

    second_major_text = ""
    if user_info.get("second_major"):
        second_major_text = f"""\nSecond Major: {user_info["second_major"]}"""

    minor_text = ""
    if user_info.get("minor"):
        minor_text = f"""\nMinor: {user_info["minor"]}"""

    second_minor_text = ""
    if user_info.get("second_minor"):
        second_minor_text = f"""\nSecond Minor: {user_info["second_minor"]}"""


    return f"""\
Name: {user_info["name"]}
Major: {user_info["major"]}{second_major_text}{minor_text}{second_minor_text}
GPA: {user_info["gpa"]}
Advisor Name: {user_info["advisor_name"]}
Advisor Email: {user_info["advisor_email"]}
Graduation Year: {user_info["grad_year"]}
Courses Taken: {user_info["courses"]}
"""