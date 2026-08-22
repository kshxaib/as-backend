from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.question_banks.schemas import QuestionBankListResponse, QuestionBankResponse, QuestionListResponse, QuestionResponse
from app.question_banks.service import add_question_to_bank, create_question_bank, extract_questions, get_question_bank, get_question_banks, get_questions
from app.questions.schemas import QuestionCreate


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


# Fetch all question banks (optionally filtered by user_id).
@router.get("", response_model=QuestionBankListResponse)
def list_question_banks_endpoint(user_id: int | None = None, db: Session = Depends(get_db)):
    question_banks = get_question_banks(db=db, user_id=user_id)
    return {
        "question_banks": question_banks,
    }


# Fetch a single question bank.
@router.get("/{question_bank_id}", response_model=QuestionBankResponse)
def get_question_bank_endpoint(question_bank_id: int, db: Session = Depends(get_db)):
    question_bank = get_question_bank(db=db, question_bank_id=question_bank_id)

    if question_bank is None:
        raise HTTPException(
            status_code=404,
            detail="Question bank not found.",
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

    except HTTPException:
        raise
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


# Add a manual question to a question bank.
@router.post("/{question_bank_id}/questions", response_model=QuestionResponse)
def add_question_endpoint(
    question_bank_id: int,
    question_data: QuestionCreate,
    db: Session = Depends(get_db),
):
    question_bank = get_question_bank(db=db, question_bank_id=question_bank_id)

    if question_bank is None:
        raise HTTPException(
            status_code=404,
            detail="Question bank not found.",
        )

    question = add_question_to_bank(
        db=db,
        question_bank_id=question_bank_id,
        question_text=question_data.question_text,
        marks=question_data.marks,
        question_number=question_data.question_number,
    )

    return question


# Download question bank original exam paper PDF as clean attachment
@router.get("/{question_bank_id}/download")
def download_question_bank_pdf_endpoint(question_bank_id: int, db: Session = Depends(get_db)):
    from fastapi import Response
    from app.storage.cloudinary import download_file_bytes

    qb = get_question_bank(db=db, question_bank_id=question_bank_id)
    if qb is None:
        raise HTTPException(status_code=404, detail="Question Bank not found.")

    try:
        content = download_file_bytes(
            public_id=qb.cloudinary_public_id,
            direct_url=qb.cloudinary_url,
            resource_type="raw",
        )
        safe_filename = f"{qb.name.replace(' ', '_')}.pdf"
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch document: {str(e)}")


