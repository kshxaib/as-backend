from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from typing import Literal

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



class QuestionBank(Base):
    __tablename__ = "question_banks"

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

    # Comma-separated resource IDs linked to this question bank.
    # Example: "3,5,12"
    resource_ids = Column(
        String,
        nullable=False,
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



class Question(Base):
    __tablename__ = "questions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    question_bank_id = Column(
        Integer,
        ForeignKey("question_banks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_number = Column(
        Integer,
        nullable=False,
    )

    question_text = Column(
        Text,
        nullable=False,
    )

    marks = Column(
        Integer,
        nullable=False,
    )

    # "explicit" — marks printed on the paper.
    # "ai_estimated" — marks guessed by the LLM.
    # "user_modified" — marks changed by the user.
    marks_source = Column(
        String(20),
        nullable=False,
        default="ai_estimated",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
