from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.db.models import Resource, AnswerSet, QuestionBank, User, Answer
from app.answers.service import format_answer_for_response


router = APIRouter(
    prefix="/api/community",
    tags=["Community Hub"],
)


class CommunityResourceItem(BaseModel):
    id: int
    user_id: int
    uploader_name: str
    name: str
    subject: str
    chapters: str | None
    description: str | None
    cloudinary_url: str
    status: str
    visibility: str
    created_at: datetime


class CommunityAnswerSetItem(BaseModel):
    id: int
    question_bank_id: int
    question_bank_name: str
    subject: str
    user_id: int
    author_name: str
    total_questions: int
    completed_questions: int
    visibility: str
    created_at: datetime


# Get all community-shared study resources
@router.get("/resources")
def get_community_resources(db: Session = Depends(get_db)):
    resources = (
        db.query(Resource, User.name.label("uploader_name"))
        .join(User, Resource.user_id == User.id, isouter=True)
        .filter(Resource.visibility == "community")
        .order_by(Resource.created_at.desc())
        .all()
    )

    items = []
    for r, uploader_name in resources:
        items.append({
            "id": r.id,
            "user_id": r.user_id,
            "uploader_name": uploader_name or "Anonymous Scholar",
            "name": r.name,
            "subject": r.subject,
            "chapters": r.chapters,
            "description": r.description,
            "cloudinary_url": r.cloudinary_url,
            "status": r.status,
            "visibility": r.visibility,
            "created_at": r.created_at,
        })

    return {"resources": items}


# Toggle share/unshare resource to community
@router.post("/resources/{resource_id}/share")
def toggle_share_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found.")

    resource.visibility = "community" if resource.visibility != "community" else "private"
    db.commit()
    db.refresh(resource)

    return {
        "message": f"Resource visibility set to {resource.visibility}",
        "resource_id": resource.id,
        "visibility": resource.visibility,
    }


# Get all community-shared solved question banks / answer sets
@router.get("/answer-sets")
def get_community_answer_sets(db: Session = Depends(get_db)):
    sets = (
        db.query(
            AnswerSet,
            QuestionBank.name.label("qb_name"),
            QuestionBank.subject.label("qb_subject"),
            User.name.label("author_name"),
        )
        .join(QuestionBank, AnswerSet.question_bank_id == QuestionBank.id)
        .join(User, AnswerSet.user_id == User.id, isouter=True)
        .filter(AnswerSet.visibility == "community")
        .order_by(AnswerSet.created_at.desc())
        .all()
    )

    items = []
    for ans_set, qb_name, qb_subject, author_name in sets:
        items.append({
            "id": ans_set.id,
            "question_bank_id": ans_set.question_bank_id,
            "question_bank_name": qb_name,
            "subject": qb_subject,
            "user_id": ans_set.user_id,
            "author_name": author_name or "AcademicStack Student",
            "total_questions": ans_set.total_questions,
            "completed_questions": ans_set.completed_questions,
            "visibility": ans_set.visibility,
            "created_at": ans_set.created_at,
        })

    return {"answer_sets": items}


# Toggle share/unshare solved answer set to community
@router.post("/answer-sets/{answer_set_id}/share")
def toggle_share_answer_set(answer_set_id: int, db: Session = Depends(get_db)):
    ans_set = db.query(AnswerSet).filter(AnswerSet.id == answer_set_id).first()
    if not ans_set:
        raise HTTPException(status_code=404, detail="Answer Set not found.")

    ans_set.visibility = "community" if ans_set.visibility != "community" else "private"
    db.commit()
    db.refresh(ans_set)

    return {
        "message": f"Answer set visibility set to {ans_set.visibility}",
        "answer_set_id": ans_set.id,
        "visibility": ans_set.visibility,
    }


# PUBLIC: Get all answers for a community-shared answer set (no login required)
@router.get("/answer-sets/{answer_set_id}/answers")
def get_community_answer_set_answers(answer_set_id: int, db: Session = Depends(get_db)):
    """
    Public read-only endpoint. Returns all formatted answers for a community-visible
    answer set. Used by the in-browser Solved Answers Viewer in The Commons.
    """
    ans_set = db.query(AnswerSet).filter(AnswerSet.id == answer_set_id).first()
    if not ans_set:
        raise HTTPException(status_code=404, detail="Answer Set not found.")

    if ans_set.visibility != "community":
        raise HTTPException(
            status_code=403,
            detail="This answer set is not publicly shared.",
        )

    qb = db.query(QuestionBank).filter(QuestionBank.id == ans_set.question_bank_id).first()
    author = db.query(User).filter(User.id == ans_set.user_id).first()

    answers = (
        db.query(Answer)
        .filter(Answer.answer_set_id == answer_set_id)
        .order_by(Answer.question_number)
        .all()
    )

    formatted = [format_answer_for_response(a) for a in answers]

    return {
        "answer_set_id": ans_set.id,
        "question_bank_id": ans_set.question_bank_id,
        "question_bank_name": qb.name if qb else "Question Bank",
        "subject": qb.subject if qb else "Subject",
        "author_name": author.name if author else "AcademicStack Student",
        "total_questions": ans_set.total_questions,
        "completed_questions": ans_set.completed_questions,
        "created_at": ans_set.created_at,
        "answers": formatted,
    }
