from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )
 
    name = Column(
        String,
        nullable=False,
    )

    gemini_api_key_encrypted = Column(
        String,
        nullable=False,
    )

    openrouter_api_key_encrypted = Column(
        String,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )