"""
This script contains the user model.
"""

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column
from user_db import Base
from sqlalchemy import String, Boolean


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    This class represents the user model with all fields.
    It is an ORM model powered by SQLAlchemy.

    Out of the box fields include:
        id (key): ID
        email: str
        hashed_password: str
        is_active: bool
        is_superuser: bool
        is_verified: bool
    """

    # filled in when user created
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # initial survey
    is_survey_complete: Mapped[Boolean | None] = mapped_column(Boolean, nullable=True)
    # other fields
