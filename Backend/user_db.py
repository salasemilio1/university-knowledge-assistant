"""
This script serves to manage most things related to user configuration with SQLAlchemy.
"""


from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from user_db import Base
from sqlalchemy import create_engine, sessionmaker, Session, select, exists, String, Boolean

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
    google_id: Mapped[str | None] = mapped_column(String(200), nullable=False, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

# create engine and session to interact with DB
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session
)

Base.metadata.create_all(bind=engine) # create tables for each ORM model if they don't already exist

# API - methods to interact with DB

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