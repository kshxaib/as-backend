import os
import uuid
import tempfile
import requests

from langchain_community.document_loaders import PyMuPDFLoader
from sqlalchemy.orm import Session

from app.db.models import QuestionBank, Question, User
from app.parsing.question_parser import parse_questions
from app.storage.cloudinary import upload_pdf, delete_pdf
from app.utils.encryption import decrypt_api_key


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

    # Step 1 — Update status.
    question_bank.status = "extracting"

    db.commit()
    db.refresh(question_bank)

    temporary_pdf_path = None

    try:
        # Step 2 — Get the owner.
        user = (
            db.query(User)
            .filter(User.id == question_bank.user_id)
            .first()
        )

        if user is None:
            raise ValueError(
                "Question bank owner was not found."
            )

        # Step 3 — Decrypt Gemini API key.
        gemini_api_key = decrypt_api_key(user.gemini_api_key_encrypted)

        # Step 4 — Create temporary PDF.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_pdf_path = temporary_file.name

        # Step 5 — Download PDF.
        download_pdf(url=question_bank.cloudinary_url, destination=temporary_pdf_path)

        # Step 6 — Extract text using PyMuPDF.
        loader = PyMuPDFLoader(temporary_pdf_path)
        documents = loader.load()

        if not documents:
            raise ValueError("No text could be extracted from the PDF.")

        full_text = ""

        for document in documents:
            if document.page_content.strip():
                full_text += document.page_content + "\n\n"

        if not full_text.strip():
            raise ValueError("PDF produced no readable text.")

        # Step 7 — Send text to Gemini for question extraction.
        parsed_questions = parse_questions(
            api_key=gemini_api_key,
            text=full_text,
        )

        if not parsed_questions:
            raise ValueError("LLM extracted zero questions.")

        # Step 8 — Delete old questions if re-extracting.
        db.query(Question).filter(
            Question.question_bank_id == question_bank.id
        ).delete()

        # Step 9 — Store extracted questions.
        for parsed in parsed_questions:
            question = Question(
                question_bank_id=question_bank.id,
                question_number=parsed["question_number"],
                question_text=parsed["question_text"],
                marks=parsed["marks"],
                marks_source=parsed["marks_source"],
            )

            db.add(question)

        # Step 10 — Mark extraction complete.
        question_bank.status = "extracted"

        db.commit()
        db.refresh(question_bank)

        return len(parsed_questions)

    except Exception:
        question_bank.status = "extraction_failed"
        db.commit()
        raise

    finally:
        # Always remove temporary PDF.
        if temporary_pdf_path and os.path.exists(temporary_pdf_path):
            os.remove(temporary_pdf_path)


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
