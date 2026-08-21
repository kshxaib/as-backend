from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.question_banks.schemas import QuestionResponse
from app.questions.schemas import QuestionUpdate
from app.questions.service import delete_question, get_question, update_question


router = APIRouter(
    prefix="/api/questions",
    tags=["Questions"],
)


# Edit a question's text or marks.
@router.put("/{question_id}", response_model=QuestionResponse)
def update_question_endpoint(
    question_id: int,
    update_data: QuestionUpdate,
    db: Session = Depends(get_db),
):

    question = get_question(db=db, question_id=question_id)

    if question is None:
        raise HTTPException(
            status_code=404,
            detail="Question not found.",
        )

    updated = update_question(
        db=db,
        question=question,
        update_data=update_data,
    )

    return updated


# Delete a question.
@router.delete("/{question_id}")
def delete_question_endpoint(question_id: int, db: Session = Depends(get_db)):

    question = get_question(db=db, question_id=question_id)

    if question is None:
        raise HTTPException(
            status_code=404,
            detail="Question not found.",
        )

    delete_question(db=db, question=question)

    return {
        "message": "Question deleted successfully.",
        "question_id": question_id,
    }
