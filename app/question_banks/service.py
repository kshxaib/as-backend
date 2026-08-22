import os
import uuid
import tempfile
import requests
import fitz  # PyMuPDF direct

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import QuestionBank, Question
from app.parsing.question_parser import parse_questions
from app.storage.cloudinary import upload_pdf
from app.users.service import get_user_openai_key


# Upload a question bank PDF to Cloudinary and store metadata.
def create_question_bank(
    db: Session, user_id: int, name: str, subject: str,
    resource_ids: str, file,
) -> QuestionBank:

    safe_name = (
        name.strip()
        .lower()
        .replace(" ", "_")
    )

    unique_id = uuid.uuid4().hex[:12]
    public_id = f"qb_{user_id}_{safe_name}_{unique_id}"

    upload_result = upload_pdf(
        file=file,
        public_id=public_id,
        folder="academicstack/question_banks",
    )

    cloudinary_url = upload_result["secure_url"]
    cloudinary_public_id = upload_result["public_id"]

    question_bank = QuestionBank(
        user_id=user_id,
        name=name,
        subject=subject,
        cloudinary_url=cloudinary_url,
        cloudinary_public_id=cloudinary_public_id,
        resource_ids=resource_ids,
        status="uploaded",
    )

    db.add(question_bank)
    db.commit()
    db.refresh(question_bank)

    return question_bank


# Download a PDF from Cloudinary.
def download_pdf(url: str, destination: str) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    with open(destination, "wb") as file:
        file.write(response.content)


# Extract questions from a question bank PDF using LLM.
def extract_questions(db: Session, question_bank: QuestionBank) -> int:
    # Step 1 — Check OpenAI API key first
    openai_api_key = get_user_openai_key(db=db, user_id=question_bank.user_id)

    # Step 2 — Update status.
    question_bank.status = "extracting"
    db.commit()
    db.refresh(question_bank)

    temporary_pdf_path = None

    try:
        # Step 3 — Create temporary PDF.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_pdf_path = temporary_file.name

        # Step 4 — Download PDF.
        download_pdf(url=question_bank.cloudinary_url, destination=temporary_pdf_path)

        # Step 5 — Extract text using PyMuPDF (layout-preserving mode).
        # We use fitz directly instead of LangChain's loader so that
        # columnar layouts (question text | marks column) are preserved.
        doc = fitz.open(temporary_pdf_path)
        full_text = ""
        for page in doc:
            # "text" flag with "blocks" preserves reading order and column structure
            page_text = page.get_text("text")
            if page_text.strip():
                full_text += page_text + "\n\n--- PAGE BREAK ---\n\n"
        doc.close()

        if not full_text.strip():
            raise ValueError("PDF produced no readable text.")


        # Step 6 — Send text to OpenAI for question extraction.
        parsed_questions = parse_questions(
            api_key=openai_api_key,
            text=full_text,
        )

        if not parsed_questions:
            raise ValueError("LLM extracted zero questions.")

        # Step 7 — Delete old questions if re-extracting.
        db.query(Question).filter(
            Question.question_bank_id == question_bank.id
        ).delete()

        # Step 8 — Store extracted questions.
        for idx, parsed in enumerate(parsed_questions, start=1):
            q_num = parsed.get("question_number")
            if not q_num or q_num <= 0:
                q_num = idx
            question = Question(
                question_bank_id=question_bank.id,
                question_number=q_num,
                question_text=parsed["question_text"],
                marks=parsed["marks"],
                marks_source=parsed["marks_source"],
            )
            db.add(question)

        # Step 9 — Mark extraction complete.
        question_bank.status = "extracted"
        db.commit()
        db.refresh(question_bank)

        return len(parsed_questions)

    except HTTPException:
        question_bank.status = "uploaded"
        db.commit()
        raise

    except Exception:
        question_bank.status = "extraction_failed"
        db.commit()
        raise

    finally:
        # Always remove temporary PDF.
        if temporary_pdf_path and os.path.exists(temporary_pdf_path):
            os.remove(temporary_pdf_path)


# Fetch multiple question banks (optionally filtered by user_id).
def get_question_banks(db: Session, user_id: int | None = None) -> list[QuestionBank]:
    query = db.query(QuestionBank)
    if user_id is not None:
        query = query.filter(QuestionBank.user_id == user_id)

    return (
        query
        .order_by(QuestionBank.created_at.desc())
        .all()
    )


# Fetch a single question bank.
def get_question_bank(db: Session, question_bank_id: int) -> QuestionBank | None:
    return (
        db.query(QuestionBank)
        .filter(QuestionBank.id == question_bank_id)
        .first()
    )


# Fetch all questions for a question bank.
def get_questions(db: Session, question_bank_id: int) -> list[Question]:
    return (
        db.query(Question)
        .filter(Question.question_bank_id == question_bank_id)
        .order_by(Question.question_number)
        .all()
    )


# Manually add a new question to a question bank.
def add_question_to_bank(
    db: Session,
    question_bank_id: int,
    question_text: str,
    marks: int,
    question_number: int | None = None,
) -> Question:
    if question_number is None:
        last_question = (
            db.query(Question)
            .filter(Question.question_bank_id == question_bank_id)
            .order_by(Question.question_number.desc())
            .first()
        )
        question_number = (last_question.question_number + 1) if last_question else 1

    question = Question(
        question_bank_id=question_bank_id,
        question_number=question_number,
        question_text=question_text,
        marks=marks,
        marks_source="user_modified",
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    return question
