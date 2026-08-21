from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.question_banks.schemas import QuestionBankResponse, QuestionListResponse
from app.question_banks.service import create_question_bank, extract_questions, get_question_bank, get_questions


router = APIRouter(
    prefix="/api/question-banks",
    tags=["Question Banks"],
)


# Upload a question bank PDF.
@router.post("", response_model=QuestionBankResponse)
def create_question_bank_endpoint(
    user_id: int = Form(...),
    name: str = Form(...),
    subject: str = Form(...),
    resource_ids: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    # Validate file.
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A file is required.",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    question_bank = create_question_bank(
        db=db,
        user_id=user_id,
        name=name,
        subject=subject,
        resource_ids=resource_ids,
        file=file,
    )

    return question_bank


# Trigger LLM question extraction.
@router.post("/{question_bank_id}/extract")
def extract_questions_endpoint(question_bank_id: int, db: Session = Depends(get_db)):

    question_bank = get_question_bank(db=db, question_bank_id=question_bank_id)

    if question_bank is None:
        raise HTTPException(
            status_code=404,
            detail="Question bank not found.",
        )

    if question_bank.status == "extracted":
        return {
            "message": "Questions already extracted. Call again to re-extract.",
            "question_bank_id": question_bank.id,
            "status": question_bank.status,
        }

    try:
        question_count = extract_questions(
            db=db,
            question_bank=question_bank,
        )

        return {
            "message": "Questions extracted successfully.",
            "question_bank_id": question_bank.id,
            "status": question_bank.status,
            "questions_extracted": question_count,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(error)}",
        )


# Get extracted questions for a question bank.
@router.get("/{question_bank_id}/questions", response_model=QuestionListResponse)
def get_questions_endpoint(question_bank_id: int, db: Session = Depends(get_db)):

    question_bank = get_question_bank(db=db, question_bank_id=question_bank_id)

    if question_bank is None:
        raise HTTPException(
            status_code=404,
            detail="Question bank not found.",
        )

    questions = get_questions(db=db, question_bank_id=question_bank_id)

    return {
        "questions": questions,
    }
