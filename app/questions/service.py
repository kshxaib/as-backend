from sqlalchemy.orm import Session

from app.db.models import Question
from app.questions.schemas import QuestionUpdate


# Fetch a single question.
def get_question(db: Session, question_id: int) -> Question | None:

    return (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )


# Update a question's text or marks.
# When marks are changed, marks_source is automatically set to "user_modified".
def update_question(db: Session, question: Question, update_data: QuestionUpdate) -> Question:

    if update_data.question_text is not None:
        question.question_text = update_data.question_text

    if update_data.marks is not None:
        question.marks = update_data.marks
        question.marks_source = "user_modified"

    db.commit()
    db.refresh(question)

    return question


# Delete a single question.
def delete_question(db: Session, question: Question) -> None:

    db.delete(question)
    db.commit()
