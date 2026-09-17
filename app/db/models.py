from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    username = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )
 
    name = Column(
        String(100),
        nullable=False,
    )

    openai_api_key_encrypted = Column(
        String,
        nullable=True,
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
    )

    files_meta = Column(
        Text,
        nullable=True,
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

    visibility = Column(
        String(20),
        nullable=False,
        default="private",
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

    repeat_count = Column(
        Integer,
        nullable=False,
        default=1,
    )

    years_appeared = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )



class AnswerSet(Base):
    __tablename__ = "answer_sets"

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

    user_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    # "generating", "completed", "failed", "completed_with_errors"
    status = Column(
        String(50),
        nullable=False,
        default="generating",
    )

    total_questions = Column(
        Integer,
        nullable=False,
        default=0,
    )

    completed_questions = Column(
        Integer,
        nullable=False,
        default=0,
    )

    visibility = Column(
        String(20),
        nullable=False,
        default="private",
    )

    pdf_url = Column(
        String,
        nullable=True,
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



class Answer(Base):
    __tablename__ = "answers"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    answer_set_id = Column(
        Integer,
        ForeignKey("answer_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
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

    repeat_count = Column(
        Integer,
        nullable=False,
        default=1,
    )

    years_appeared = Column(
        String,
        nullable=True,
    )

    # Generated Markdown answer
    content = Column(
        Text,
        nullable=True,
    )

    # JSON array string of cited sources: [{"resource_name": "...", "page": 4, "chapter": "..."}]
    sources = Column(
        Text,
        nullable=True,
    )

    # "pending", "generating", "completed", "failed"
    status = Column(
        String(50),
        nullable=False,
        default="pending",
    )

    error_message = Column(
        Text,
        nullable=True,
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


class SharedPredictedPaper(Base):
    __tablename__ = "shared_predicted_papers"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    share_token = Column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    user_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    creator_name = Column(
        String(100),
        nullable=False,
        default="Student Scholar",
    )

    subject = Column(
        String(100),
        nullable=False,
    )

    title = Column(
        String(200),
        nullable=False,
    )

    paper_data = Column(
        Text,
        nullable=False,
    )

    views = Column(
        Integer,
        default=0,
        nullable=False,
    )

    visibility = Column(
        String(20),
        default="private",
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
