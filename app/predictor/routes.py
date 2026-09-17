"""
FastAPI router for Multi-Paper Analysis & Predicted Question Paper Generation.
"""

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import QuestionBank, Question
from app.users.service import get_user_all_keys, check_user_has_all_required_keys
from app.predictor.service import (
    extract_text_from_pdf_bytes,
    analyze_and_predict_paper,
    save_predicted_paper_as_question_bank,
)
from app.pdf.predicted_paper_generator import generate_predicted_question_paper_pdf

logger = logging.getLogger("academicstack.predictor.routes")

router = APIRouter(
    prefix="/api/predictor",
    tags=["Exam Paper Predictor"],
)


@router.post("/generate")
async def generate_predicted_paper(
    subject: str = Form(...),
    title: str = Form(...),
    user_id: int = Form(...),
    papers_meta: str = Form(default="[]"),
    existing_qb_ids: str = Form(default=""),
    existing_qbs_meta: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    """
    Analyzes multiple past exam papers and synthesizes a predicted model question paper.
    Supports up to 10 past exam papers (uploaded files + existing question banks).
    """
    # 1. Verify user keys
    check_user_has_all_required_keys(db=db, user_id=user_id)
    user_keys = get_user_all_keys(db=db, user_id=user_id)

    # 2. Parse metadata
    try:
        meta_list = json.loads(papers_meta)
    except Exception:
        meta_list = []

    # Map of QB id -> custom session label
    existing_qbs_session_map = {}
    try:
        qbs_meta_list = json.loads(existing_qbs_meta)
        for item in qbs_meta_list:
            if isinstance(item, dict) and "id" in item:
                existing_qbs_session_map[int(item["id"])] = item.get("session", "")
    except Exception:
        pass

    collected_papers = []

    # 3. Read uploaded files (up to max 10)
    for idx, uploaded_file in enumerate(files):
        if len(collected_papers) >= 10:
            break

        file_bytes = await uploaded_file.read()
        extracted_text = extract_text_from_pdf_bytes(file_bytes, uploaded_file.filename or f"Paper_{idx+1}.pdf")
        
        session_label = f"Exam Paper #{idx+1}"
        if idx < len(meta_list) and meta_list[idx].get("session"):
            session_label = meta_list[idx]["session"]

        if extracted_text.strip():
            collected_papers.append({
                "session": session_label,
                "filename": uploaded_file.filename or f"Paper_{idx+1}.pdf",
                "text": extracted_text,
            })

    # 4. Include existing Question Banks if selected
    if existing_qb_ids.strip():
        qb_id_list = [int(x.strip()) for x in existing_qb_ids.split(",") if x.strip().isdigit()]
        for qb_id in qb_id_list:
            if len(collected_papers) >= 10:
                break
            qb = db.query(QuestionBank).filter(QuestionBank.id == qb_id).first()
            if qb:
                qs = db.query(Question).filter(Question.question_bank_id == qb_id).order_by(Question.question_number).all()
                if qs:
                    lines = [f"Q{q.question_number}. {q.question_text} [{q.marks} Marks]" for q in qs]
                    custom_session = existing_qbs_session_map.get(qb.id)
                    session_label = custom_session.strip() if custom_session else qb.name

                    collected_papers.append({
                        "session": session_label,
                        "filename": f"QuestionBank_{qb.name}.txt",
                        "text": "\n".join(lines),
                    })

    if not collected_papers:
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the provided exam papers. Please upload valid question paper PDFs.",
        )

    try:
        predicted_paper = analyze_and_predict_paper(
            subject=subject.strip(),
            title=title.strip(),
            papers=collected_papers,
            user_keys=user_keys,
        )
        return predicted_paper
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"AI Paper Prediction failed: {str(e)}",
        )


@router.post("/save-as-qb")
def save_as_qb_endpoint(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Saves the predicted paper into the student's Question Banks repository.
    """
    user_id = payload.get("user_id")
    paper_data = payload.get("paper_data")

    if not user_id or not paper_data:
        raise HTTPException(status_code=400, detail="user_id and paper_data are required.")

    try:
        qb = save_predicted_paper_as_question_bank(db=db, user_id=int(user_id), paper_data=paper_data)
        return {
            "success": True,
            "question_bank_id": qb.id,
            "name": qb.name,
            "subject": qb.subject,
            "message": "Predicted paper saved to Question Banks successfully.",
        }
    except Exception as e:
        logger.error(f"Failed to save predicted paper as QuestionBank: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf")
def export_predicted_paper_pdf(payload: dict):
    """
    Generates and returns an authentic university examination paper PDF.
    """
    paper_data = payload.get("paper_data")
    if not paper_data:
        raise HTTPException(status_code=400, detail="paper_data is required.")

    try:
        pdf_bytes = generate_predicted_question_paper_pdf(paper_data)
        meta = paper_data.get("exam_meta", {})
        title = meta.get("paper_title", "Predicted_Paper").replace(" ", "_")
        safe_filename = f"{title}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Content-Type": "application/pdf",
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate predicted paper PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
