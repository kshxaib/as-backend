import json
from sqlalchemy.orm import Session

from app.db.models import Answer, AnswerSet, Question, QuestionBank, User
from app.rag.service import generate_rag_answer
from app.utils.encryption import decrypt_api_key


def parse_resource_ids(resource_ids_str: str) -> list[int]:
    if not resource_ids_str:
        return []
    ids = []
    for part in resource_ids_str.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def get_user_openai_key(db: Session, user_id: int) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")
    return decrypt_api_key(user.openai_api_key_encrypted)


def generate_answer_set(db: Session, question_bank_id: int, user_id: int | None = None) -> AnswerSet:
    # 1. Fetch Question Bank & Questions
    qb = db.query(QuestionBank).filter(QuestionBank.id == question_bank_id).first()
    if not qb:
        raise ValueError(f"Question Bank with ID {question_bank_id} not found.")

    effective_user_id = user_id or qb.user_id
    openai_key = get_user_openai_key(db, effective_user_id)
    resource_ids = parse_resource_ids(qb.resource_ids)

    questions = (
        db.query(Question)
        .filter(Question.question_bank_id == question_bank_id)
        .order_by(Question.question_number)
        .all()
    )

    if not questions:
        raise ValueError("No questions found in this Question Bank to generate answers for.")

    # 2. Create AnswerSet record
    answer_set = AnswerSet(
        question_bank_id=question_bank_id,
        user_id=effective_user_id,
        status="generating",
        total_questions=len(questions),
        completed_questions=0,
    )
    db.add(answer_set)
    db.commit()
    db.refresh(answer_set)

    # 3. Create initial pending Answer records
    answer_records = []
    for q in questions:
        ans = Answer(
            answer_set_id=answer_set.id,
            question_id=q.id,
            question_number=q.question_number,
            question_text=q.question_text,
            marks=q.marks,
            status="pending",
        )
        db.add(ans)
        answer_records.append(ans)

    db.commit()

    # 4. Generate answers sequentially
    has_failures = False
    for ans in answer_records:
        ans.status = "generating"
        db.commit()

        try:
            rag_output = generate_rag_answer(
                openai_api_key=openai_key,
                question_text=ans.question_text,
                marks=ans.marks,
                resource_ids=resource_ids,
            )
            ans.content = rag_output["content"]
            ans.sources = json.dumps(rag_output["sources"])
            ans.status = "completed"
            ans.error_message = None
            answer_set.completed_questions += 1
        except Exception as error:
            has_failures = True
            ans.status = "failed"
            ans.error_message = str(error)

        db.commit()

    # 5. Finalize status
    answer_set.status = "completed" if not has_failures else "completed_with_errors"
    db.commit()
    db.refresh(answer_set)

    return answer_set


def retry_single_answer(db: Session, answer_id: int) -> Answer:
    ans = db.query(Answer).filter(Answer.id == answer_id).first()
    if not ans:
        raise ValueError(f"Answer with ID {answer_id} not found.")

    answer_set = db.query(AnswerSet).filter(AnswerSet.id == ans.answer_set_id).first()
    if not answer_set:
        raise ValueError(f"AnswerSet with ID {ans.answer_set_id} not found.")

    qb = db.query(QuestionBank).filter(QuestionBank.id == answer_set.question_bank_id).first()
    openai_key = get_user_openai_key(db, answer_set.user_id)
    resource_ids = parse_resource_ids(qb.resource_ids) if qb else []

    was_previously_completed = ans.status == "completed"
    ans.status = "generating"
    db.commit()

    try:
        rag_output = generate_rag_answer(
            openai_api_key=openai_key,
            question_text=ans.question_text,
            marks=ans.marks,
            resource_ids=resource_ids,
        )
        ans.content = rag_output["content"]
        ans.sources = json.dumps(rag_output["sources"])
        ans.status = "completed"
        ans.error_message = None

        if not was_previously_completed and answer_set.completed_questions < answer_set.total_questions:
            answer_set.completed_questions += 1

        db.commit()
        db.refresh(ans)
        return ans
    except Exception as error:
        ans.status = "failed"
        ans.error_message = str(error)
        db.commit()
        raise


def get_answer_set(db: Session, answer_set_id: int) -> AnswerSet | None:
    return db.query(AnswerSet).filter(AnswerSet.id == answer_set_id).first()


def get_answers_for_set(db: Session, answer_set_id: int) -> list[Answer]:
    return (
        db.query(Answer)
        .filter(Answer.answer_set_id == answer_set_id)
        .order_by(Answer.question_number)
        .all()
    )


def format_answer_for_response(ans: Answer) -> dict:
    sources_list = []
    if ans.sources:
        try:
            sources_list = json.loads(ans.sources)
        except Exception:
            sources_list = []

    return {
        "id": ans.id,
        "answer_set_id": ans.answer_set_id,
        "question_id": ans.question_id,
        "question_number": ans.question_number,
        "question_text": ans.question_text,
        "marks": ans.marks,
        "content": ans.content,
        "sources": sources_list,
        "status": ans.status,
        "error_message": ans.error_message,
        "created_at": ans.created_at,
        "updated_at": ans.updated_at,
    }
