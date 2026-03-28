"""
This script contains the user model.
"""

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column
from user_db import Base
import string


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    This class represents the user model with all fields.
    It is an ORM model powered by SQLAlchemy.
    """