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



class Resource(Base):
    __tablename__ = "resources"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    subject = Column(
        String(100),
        nullable=False,
    )

    chapters = Column(
        String,
        nullable=True,
    )

    description = Column(
        String(1000),
        nullable=True,
    )

    cloudinary_url = Column(
        String,
        nullable=False,
    )

    cloudinary_public_id = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    visibility = Column(
        String(20),
        nullable=False,
        default="private",
    )

    status = Column(
        String(20),
        nullable=False,
        default="uploaded",
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



