from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.answers.schemas import AnswerResponse, AnswerSetProgressResponse, AnswerSetResponse, GenerateAnswerSetRequest, RetryAnswerRequest
from app.answers.service import format_answer_for_response, generate_answer_set, get_answer_set, get_answers_for_set, retry_single_answer
from app.db.database import get_db
from app.db.models import AnswerSet, QuestionBank
from app.pdf.generator import generate_solved_question_bank_pdf

router = APIRouter(
    prefix="/api",
    tags=["Answers & Generation"],
)


# Generate answers for an entire Question Bank
@router.post("/answer-sets/generate", response_model=AnswerSetResponse)
def generate_answer_set_endpoint(
    payload: GenerateAnswerSetRequest,
    db: Session = Depends(get_db),
):
    try:
        answer_set = generate_answer_set(
            db=db,
            question_bank_id=payload.question_bank_id,
            user_id=payload.user_id,
        )
        answers = get_answers_for_set(db=db, answer_set_id=answer_set.id)
        formatted_answers = [format_answer_for_response(a) for a in answers]

        return {
            "id": answer_set.id,
            "question_bank_id": answer_set.question_bank_id,
            "user_id": answer_set.user_id,
            "status": answer_set.status,
            "total_questions": answer_set.total_questions,
            "completed_questions": answer_set.completed_questions,
            "created_at": answer_set.created_at,
            "updated_at": answer_set.updated_at,
            "answers": formatted_answers,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Answer generation failed: {str(error)}")


# Get full Answer Set with all answers
@router.get("/answer-sets/{answer_set_id}", response_model=AnswerSetResponse)
def get_answer_set_endpoint(
    answer_set_id: int,
    db: Session = Depends(get_db),
):
    answer_set = get_answer_set(db=db, answer_set_id=answer_set_id)
    if not answer_set:
        raise HTTPException(status_code=404, detail="Answer Set not found.")

    answers = get_answers_for_set(db=db, answer_set_id=answer_set.id)
    formatted_answers = [format_answer_for_response(a) for a in answers]

    return {
        "id": answer_set.id,
        "question_bank_id": answer_set.question_bank_id,
        "user_id": answer_set.user_id,
        "status": answer_set.status,
        "total_questions": answer_set.total_questions,
        "completed_questions": answer_set.completed_questions,
        "created_at": answer_set.created_at,
        "updated_at": answer_set.updated_at,
        "answers": formatted_answers,
    }


# Download Solved Question Bank as PDF (Phase 8)
@router.get("/answer-sets/{answer_set_id}/pdf")
def download_answer_set_pdf_endpoint(
    answer_set_id: int,
    db: Session = Depends(get_db),
):
    answer_set = get_answer_set(db=db, answer_set_id=answer_set_id)
    if not answer_set:
        raise HTTPException(status_code=404, detail="Answer Set not found.")

    qb = db.query(QuestionBank).filter(QuestionBank.id == answer_set.question_bank_id).first()
    qb_name = qb.name if qb else "Solved Question Bank"
    subject = qb.subject if qb else "Academic Subject"

    answers = get_answers_for_set(db=db, answer_set_id=answer_set.id)
    formatted_answers = [format_answer_for_response(a) for a in answers]

    pdf_bytes = generate_solved_question_bank_pdf(
        question_bank_name=qb_name,
        subject=subject,
        answers=formatted_answers,
    )

    safe_filename = f"AcademicStack_{subject.replace(' ', '_')}_{qb_name.replace(' ', '_')}_Solved.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )


# Check generation progress
@router.get("/answer-sets/{answer_set_id}/progress", response_model=AnswerSetProgressResponse)
def get_answer_set_progress_endpoint(
    answer_set_id: int,
    db: Session = Depends(get_db),
):
    answer_set = get_answer_set(db=db, answer_set_id=answer_set_id)
    if not answer_set:
        raise HTTPException(status_code=404, detail="Answer Set not found.")

    progress = 0.0
    if answer_set.total_questions > 0:
        progress = round((answer_set.completed_questions / answer_set.total_questions) * 100, 1)

    return {
        "id": answer_set.id,
        "question_bank_id": answer_set.question_bank_id,
        "status": answer_set.status,
        "total_questions": answer_set.total_questions,
        "completed_questions": answer_set.completed_questions,
        "progress_percentage": progress,
    }


# Retry a single failed answer (optionally with a user-supplied instruction)
@router.post("/answers/{answer_id}/retry", response_model=AnswerResponse)
def retry_answer_endpoint(
    answer_id: int,
    payload: RetryAnswerRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    try:
        ans = retry_single_answer(
            db=db,
            answer_id=answer_id,
            user_instruction=payload.user_instruction if payload else None,
            reference_answer=payload.reference_answer if payload else None,
        )
        return format_answer_for_response(ans)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Retry failed: {str(error)}")


# List all answer sets for a question bank
@router.get("/question-banks/{question_bank_id}/answer-sets")
def list_answer_sets_for_bank_endpoint(
    question_bank_id: int,
    db: Session = Depends(get_db),
):
    answer_sets = (
        db.query(AnswerSet)
        .filter(AnswerSet.question_bank_id == question_bank_id)
        .order_by(AnswerSet.created_at.desc())
        .all()
    )
    return {"answer_sets": answer_sets}
