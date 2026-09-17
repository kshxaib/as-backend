from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.db.models import Resource, AnswerSet, QuestionBank, User, Answer, SharedPredictedPaper, Question
from app.core.security import get_current_user
from app.predictor.service import save_predicted_paper_as_question_bank
import json
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


# Share an updated/regenerated answer set as the SINGLE community copy for its
# question bank, retiring any previously-shared version so the Hub never shows
# a duplicate of the same bank.
@router.post("/answer-sets/{answer_set_id}/share-update")
def share_updated_answer_set(answer_set_id: int, db: Session = Depends(get_db)):
    ans_set = db.query(AnswerSet).filter(AnswerSet.id == answer_set_id).first()
    if not ans_set:
        raise HTTPException(status_code=404, detail="Answer Set not found.")

    # Retire any other community-shared set for the same question bank + owner.
    stale_sets = (
        db.query(AnswerSet)
        .filter(
            AnswerSet.question_bank_id == ans_set.question_bank_id,
            AnswerSet.user_id == ans_set.user_id,
            AnswerSet.visibility == "community",
            AnswerSet.id != ans_set.id,
        )
        .all()
    )
    retired_ids = []
    for stale in stale_sets:
        stale.visibility = "private"
        retired_ids.append(stale.id)

    # Point the community flag at this (updated) set.
    ans_set.visibility = "community"
    db.commit()
    db.refresh(ans_set)

    return {
        "message": "Updated answer set shared to The Commons.",
        "answer_set_id": ans_set.id,
        "visibility": ans_set.visibility,
        "retired_ids": retired_ids,
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


# ─── Predicted Papers in The Commons ──────────────────────────────────────────

# Get all community-shared predicted papers
@router.get("/predicted-papers")
def get_community_predicted_papers(db: Session = Depends(get_db)):
    papers = (
        db.query(SharedPredictedPaper, User.name.label("user_name"))
        .outerjoin(User, SharedPredictedPaper.user_id == User.id)
        .filter(SharedPredictedPaper.visibility == "community")
        .order_by(SharedPredictedPaper.created_at.desc())
        .all()
    )

    items = []
    for paper, user_name in papers:
        # Parse exam_meta from paper_data for display info
        try:
            parsed = json.loads(paper.paper_data) if isinstance(paper.paper_data, str) else paper.paper_data
            meta = parsed.get("exam_meta", {})
        except Exception:
            meta = {}

        items.append({
            "id": paper.id,
            "share_token": paper.share_token,
            "user_id": paper.user_id,
            "creator_name": paper.creator_name or user_name or "Student Scholar",
            "subject": paper.subject,
            "title": paper.title,
            "time_allowed": meta.get("time_allowed", ""),
            "maximum_marks": meta.get("maximum_marks", ""),
            "views": paper.views,
            "visibility": paper.visibility,
            "created_at": paper.created_at.isoformat() if paper.created_at else None,
        })

    return {"predicted_papers": items}


# Get full predicted paper data for community viewer
@router.get("/predicted-papers/{paper_id}")
def get_community_predicted_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(SharedPredictedPaper).filter(SharedPredictedPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Predicted paper not found.")

    if paper.visibility != "community":
        raise HTTPException(status_code=403, detail="This predicted paper is not publicly shared.")

    paper.views += 1
    db.commit()

    try:
        parsed_data = json.loads(paper.paper_data) if isinstance(paper.paper_data, str) else paper.paper_data
    except Exception:
        parsed_data = {}

    author = db.query(User).filter(User.id == paper.user_id).first() if paper.user_id else None

    return {
        "id": paper.id,
        "share_token": paper.share_token,
        "creator_name": paper.creator_name or (author.name if author else "Student Scholar"),
        "subject": paper.subject,
        "title": paper.title,
        "views": paper.views,
        "visibility": paper.visibility,
        "created_at": paper.created_at.isoformat() if paper.created_at else None,
        "paper_data": parsed_data,
    }


# Toggle share/unshare predicted paper to community
@router.post("/predicted-papers/{paper_id}/toggle-share")
def toggle_share_predicted_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(SharedPredictedPaper).filter(SharedPredictedPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Predicted paper not found.")

    paper.visibility = "community" if paper.visibility != "community" else "private"
    db.commit()
    db.refresh(paper)

    return {
        "message": f"Predicted paper visibility set to {paper.visibility}",
        "id": paper.id,
        "visibility": paper.visibility,
    }


# =====================================================================
# Curated Question Banks (PYQ Collections) Endpoints
# =====================================================================

# Get all community-shared extracted question banks
@router.get("/question-banks")
def get_community_question_banks(db: Session = Depends(get_db)):
    qbs = (
        db.query(
            QuestionBank,
            User.name.label("author_name"),
            func.count(Question.id).label("total_questions"),
            func.coalesce(func.sum(Question.marks), 0).label("total_marks"),
        )
        .join(User, QuestionBank.user_id == User.id, isouter=True)
        .outerjoin(Question, QuestionBank.id == Question.question_bank_id)
        .filter(QuestionBank.visibility == "community")
        .group_by(QuestionBank.id, User.name)
        .order_by(QuestionBank.created_at.desc())
        .all()
    )

    items = []
    for qb, author_name, total_q, total_marks in qbs:
        items.append({
            "id": qb.id,
            "user_id": qb.user_id,
            "name": qb.name,
            "subject": qb.subject,
            "author_name": author_name or "Student Scholar",
            "status": qb.status,
            "total_questions": int(total_q or 0),
            "total_marks": int(total_marks or 0),
            "cloudinary_url": qb.cloudinary_url,
            "visibility": qb.visibility,
            "created_at": qb.created_at.isoformat() if qb.created_at else None,
        })

    return {"question_banks": items}


# Toggle share/unshare question bank to community (only owner can share/unshare)
@router.post("/question-banks/{qb_id}/share")
def toggle_share_question_bank(
    qb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qb = db.query(QuestionBank).filter(QuestionBank.id == qb_id).first()
    if not qb:
        raise HTTPException(status_code=404, detail="Question bank not found.")

    if qb.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only share or unshare question banks you created.")

    qb.visibility = "community" if qb.visibility != "community" else "private"
    db.commit()
    db.refresh(qb)

    return {
        "message": f"Question bank visibility set to {qb.visibility}",
        "id": qb.id,
        "visibility": qb.visibility,
    }


# PUBLIC: Get all questions for a community-shared question bank
@router.get("/question-banks/{qb_id}/questions")
def get_community_question_bank_questions(qb_id: int, db: Session = Depends(get_db)):
    qb = db.query(QuestionBank).filter(QuestionBank.id == qb_id).first()
    if not qb:
        raise HTTPException(status_code=404, detail="Question bank not found.")

    if qb.visibility != "community":
        raise HTTPException(status_code=403, detail="This question bank is not publicly shared.")

    author = db.query(User).filter(User.id == qb.user_id).first()
    questions = (
        db.query(Question)
        .filter(Question.question_bank_id == qb_id)
        .order_by(Question.question_number.asc())
        .all()
    )

    return {
        "question_bank": {
            "id": qb.id,
            "name": qb.name,
            "subject": qb.subject,
            "author_name": author.name if author else "Student Scholar",
            "total_questions": len(questions),
            "total_marks": sum(q.marks for q in questions if q.marks),
            "created_at": qb.created_at.isoformat() if qb.created_at else None,
        },
        "questions": [
            {
                "id": q.id,
                "question_number": q.question_number,
                "question_text": q.question_text,
                "marks": q.marks,
                "marks_source": q.marks_source,
                "repeat_count": q.repeat_count,
                "years_appeared": q.years_appeared,
            }
            for q in questions
        ],
    }


# Clone / Fork community question bank to classmate's personal workspace
@router.post("/question-banks/{qb_id}/clone")
def clone_community_question_bank(
    qb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source_qb = db.query(QuestionBank).filter(QuestionBank.id == qb_id).first()
    if not source_qb:
        raise HTTPException(status_code=404, detail="Question bank not found.")
    if source_qb.visibility != "community" and source_qb.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This question bank is not publicly shared.")

    author = db.query(User).filter(User.id == source_qb.user_id).first()
    author_name = author.name if author else "Peer"

    cloned_name = f"{source_qb.name} (from @{author_name})"
    cloned_qb = QuestionBank(
        user_id=current_user.id,
        name=cloned_name,
        subject=source_qb.subject,
        cloudinary_url=source_qb.cloudinary_url,
        cloudinary_public_id=source_qb.cloudinary_public_id,
        files_meta=source_qb.files_meta,
        resource_ids=source_qb.resource_ids or "",
        status=source_qb.status,
        visibility="private",
    )
    db.add(cloned_qb)
    db.flush()

    source_questions = (
        db.query(Question)
        .filter(Question.question_bank_id == source_qb.id)
        .order_by(Question.question_number.asc())
        .all()
    )
    for q in source_questions:
        cloned_q = Question(
            question_bank_id=cloned_qb.id,
            question_number=q.question_number,
            question_text=q.question_text,
            marks=q.marks,
            marks_source=q.marks_source,
            repeat_count=q.repeat_count,
            years_appeared=q.years_appeared,
        )
        db.add(cloned_q)

    db.commit()
    db.refresh(cloned_qb)

    return {
        "message": f"Successfully cloned '{source_qb.name}' to your Question Banks.",
        "question_bank": {
            "id": cloned_qb.id,
            "name": cloned_qb.name,
            "subject": cloned_qb.subject,
            "status": cloned_qb.status,
            "total_questions": len(source_questions),
        }
    }


# Clone / Fork community solved answer set to classmate's personal workspace
@router.post("/answer-sets/{answer_set_id}/clone")
def clone_community_answer_set(
    answer_set_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source_ans_set = db.query(AnswerSet).filter(AnswerSet.id == answer_set_id).first()
    if not source_ans_set:
        raise HTTPException(status_code=404, detail="Answer set not found.")

    if source_ans_set.visibility != "community" and source_ans_set.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This solved answer set is not publicly shared.")

    source_qb = db.query(QuestionBank).filter(QuestionBank.id == source_ans_set.question_bank_id).first()
    if not source_qb:
        raise HTTPException(status_code=404, detail="Underlying question bank not found.")

    author = db.query(User).filter(User.id == source_ans_set.user_id).first()
    author_name = author.name if author else "Peer"

    # 1. Clone the QuestionBank
    cloned_qb_name = f"{source_qb.name} (Solved from @{author_name})"
    cloned_qb = QuestionBank(
        user_id=current_user.id,
        name=cloned_qb_name,
        subject=source_qb.subject,
        cloudinary_url=source_qb.cloudinary_url,
        cloudinary_public_id=source_qb.cloudinary_public_id,
        files_meta=source_qb.files_meta,
        resource_ids=source_qb.resource_ids or "",
        status="extracted",
        visibility="private",
    )
    db.add(cloned_qb)
    db.flush()

    # 2. Clone all Questions and build old_id -> new_id map
    source_questions = (
        db.query(Question)
        .filter(Question.question_bank_id == source_qb.id)
        .order_by(Question.question_number.asc())
        .all()
    )
    old_to_new_q_map = {}
    for q in source_questions:
        cloned_q = Question(
            question_bank_id=cloned_qb.id,
            question_number=q.question_number,
            question_text=q.question_text,
            marks=q.marks,
            marks_source=q.marks_source,
            repeat_count=q.repeat_count,
            years_appeared=q.years_appeared,
        )
        db.add(cloned_q)
        db.flush()
        old_to_new_q_map[q.id] = cloned_q.id

    # 3. Clone AnswerSet
    cloned_ans_set = AnswerSet(
        question_bank_id=cloned_qb.id,
        user_id=current_user.id,
        status=source_ans_set.status,
        total_questions=source_ans_set.total_questions,
        completed_questions=source_ans_set.completed_questions,
        visibility="private",
        pdf_url=source_ans_set.pdf_url,
    )
    db.add(cloned_ans_set)
    db.flush()

    # 4. Clone all Answer rows
    source_answers = (
        db.query(Answer)
        .filter(Answer.answer_set_id == source_ans_set.id)
        .order_by(Answer.question_number.asc())
        .all()
    )
    for ans in source_answers:
        new_q_id = old_to_new_q_map.get(ans.question_id)
        if not new_q_id:
            fallback_q = db.query(Question).filter(
                Question.question_bank_id == cloned_qb.id,
                Question.question_number == ans.question_number,
            ).first()
            new_q_id = fallback_q.id if fallback_q else None

        if new_q_id:
            cloned_ans = Answer(
                answer_set_id=cloned_ans_set.id,
                question_id=new_q_id,
                question_number=ans.question_number,
                question_text=ans.question_text,
                marks=ans.marks,
                repeat_count=ans.repeat_count,
                years_appeared=ans.years_appeared,
                content=ans.content,
                sources=ans.sources,
                status=ans.status,
                error_message=ans.error_message,
            )
            db.add(cloned_ans)

    db.commit()
    db.refresh(cloned_qb)
    db.refresh(cloned_ans_set)

    return {
        "message": f"Successfully cloned solved question bank '{source_qb.name}' with solutions to your workspace.",
        "question_bank_id": cloned_qb.id,
        "answer_set_id": cloned_ans_set.id,
        "total_questions": len(source_questions),
        "completed_answers": len(source_answers),
    }


# Clone / Fork community predicted paper into classmate's personal workspace
@router.post("/predicted-papers/{paper_id}/clone")
def clone_community_predicted_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = db.query(SharedPredictedPaper).filter(SharedPredictedPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Predicted paper not found.")

    if paper.visibility != "community" and paper.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This predicted paper is not publicly shared.")

    try:
        parsed_data = json.loads(paper.paper_data) if isinstance(paper.paper_data, str) else paper.paper_data
    except Exception:
        raise HTTPException(status_code=500, detail="Malformed paper data.")

    author = db.query(User).filter(User.id == paper.user_id).first() if paper.user_id else None
    author_name = paper.creator_name or (author.name if author else "Scholar")

    cloned_title = f"{paper.title or 'Predicted Exam Paper'} (from @{author_name})"
    
    if "exam_meta" in parsed_data:
        parsed_data["exam_meta"]["paper_title"] = cloned_title

    cloned_qb = save_predicted_paper_as_question_bank(
        db=db,
        user_id=current_user.id,
        paper_data=parsed_data,
    )
    cloned_qb.name = cloned_title
    cloned_qb.visibility = "private"
    db.commit()
    db.refresh(cloned_qb)

    q_count = db.query(Question).filter(Question.question_bank_id == cloned_qb.id).count()

    return {
        "message": f"Successfully cloned predicted paper '{paper.title}' to your Question Banks.",
        "question_bank": {
            "id": cloned_qb.id,
            "name": cloned_qb.name,
            "subject": cloned_qb.subject,
            "status": cloned_qb.status,
            "total_questions": q_count,
        }
    }


