import os
import uuid
import tempfile
import requests
import pymupdf as fitz
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import QuestionBank, Question, Resource
from app.parsing.question_parser import parse_questions
from app.storage.cloudinary import upload_pdf, download_file_bytes
from app.users.service import get_user_all_keys, check_user_has_all_required_keys
from app.rag.embeddings import create_embedding_model
import numpy as np


def create_question_bank(
    db: Session, user_id: int, name: str, subject: str,
    resource_ids: str, files: list
) -> QuestionBank:
    safe_name = (
        name.strip()
        .lower()
        .replace(" ", "_")
    )

    unique_id = uuid.uuid4().hex[:12]
    
    files_meta_data = []
    
    for i, file in enumerate(files):
        public_id = f"qb_{user_id}_{safe_name}_{unique_id}_{i}"
        
        upload_result = upload_pdf(
            file=file,
            public_id=public_id,
            folder="academicstack/question_banks",
        )
        
        files_meta_data.append({
            "filename": file.filename,
            "url": upload_result["secure_url"],
            "public_id": upload_result["public_id"]
        })

    # For backward compatibility, store the first file's details in the old columns
    first_file = files_meta_data[0] if files_meta_data else {"url": "", "public_id": ""}
    
    question_bank = QuestionBank(
        user_id=user_id,
        name=name,
        subject=subject,
        cloudinary_url=first_file.get("url", ""),
        cloudinary_public_id=first_file.get("public_id", ""),
        files_meta=json.dumps(files_meta_data),
        resource_ids=resource_ids,
        status="uploaded",
    )

    db.add(question_bank)
    db.commit()
    db.refresh(question_bank)

    return question_bank


def download_pdf(public_id: str, direct_url: str, destination: str) -> None:
    content = download_file_bytes(public_id=public_id, direct_url=direct_url)
    with open(destination, "wb") as file:
        file.write(content)


def extract_questions(db: Session, question_bank: QuestionBank) -> int:
    # 1. Verify user has configured all 4 required free keys
    check_user_has_all_required_keys(db=db, user_id=question_bank.user_id)
    user_keys = get_user_all_keys(db=db, user_id=question_bank.user_id)

    # 2. Update status
    question_bank.status = "extracting"
    db.commit()
    db.refresh(question_bank)

    try:
        # Check for multiple files
        files_data = []
        if question_bank.files_meta:
            try:
                files_data = json.loads(question_bank.files_meta)
            except Exception:
                pass
        
        if not files_data:
            files_data = [{"url": question_bank.cloudinary_url, "public_id": question_bank.cloudinary_public_id, "filename": "Question_Paper.pdf"}]

        all_parsed_questions = []
        temp_paths = []

        try:
            for fd in files_data:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
                    temp_paths.append(temporary_file.name)
                
                download_pdf(public_id=fd["public_id"], direct_url=fd["url"], destination=temporary_file.name)
                
                doc = fitz.open(temporary_file.name)
                full_text = f"--- SOURCE FILE: {fd.get('filename', 'Unknown')} ---\n\n"
                for page in doc:
                    page_text = page.get_text("text")
                    if page_text.strip():
                        full_text += page_text + "\n\n--- PAGE BREAK ---\n\n"
                doc.close()

                if not full_text.strip():
                    continue

                parsed = parse_questions(text=full_text, user_keys=user_keys)
                if parsed:
                    # Tag parsed questions with source filename
                    for p in parsed:
                        p["source_filename"] = fd.get("filename", "Unknown")
                    all_parsed_questions.extend(parsed)
                    
        finally:
            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)

        if not all_parsed_questions:
            raise ValueError("LLM extracted zero questions from all files.")

        parsed_questions = all_parsed_questions

        # 7. Deduplicate using OpenAI embeddings
        embeddings_model = create_embedding_model(user_keys)
        
        texts_to_embed = [q["question_text"] for q in parsed_questions]
        embedded_vectors = embeddings_model.embed_documents(texts_to_embed)
        
        # Convert to numpy array and normalize
        vectors = np.array(embedded_vectors)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors_normalized = vectors / np.where(norms == 0, 1e-10, norms)
        
        # Calculate pairwise cosine similarity
        similarity_matrix = np.dot(vectors_normalized, vectors_normalized.T)
        
        # Get resource names to build years_appeared string
        resource_ids = [int(rid.strip()) for rid in question_bank.resource_ids.split(",") if rid.strip()]
        resources = db.query(Resource).filter(Resource.id.in_(resource_ids)).all()
        resource_names = ", ".join([r.name for r in resources])

        # Grouping logic
        merged_questions = []
        visited = set()
        
        for i, q in enumerate(parsed_questions):
            if i in visited:
                continue
            
            cluster = [i]
            visited.add(i)
            
            for j in range(i + 1, len(parsed_questions)):
                if j not in visited and similarity_matrix[i, j] >= 0.72:
                    cluster.append(j)
                    visited.add(j)
                    
            # Merge cluster
            best_text = max([parsed_questions[idx]["question_text"] for idx in cluster], key=len)
            max_marks = max([parsed_questions[idx]["marks"] for idx in cluster])
            
            # Get unique filenames for this cluster
            cluster_filenames = list(set([parsed_questions[idx].get("source_filename", "Unknown") for idx in cluster]))
            years_appeared_str = ", ".join(cluster_filenames)
            
            merged_questions.append({
                "question_text": best_text,
                "marks": max_marks,
                "marks_source": parsed_questions[i]["marks_source"],
                "repeat_count": len(cluster),
                "years_appeared": years_appeared_str if len(cluster) > 1 else None,
            })

        # 8. Delete old questions if re-extracting
        db.query(Question).filter(
            Question.question_bank_id == question_bank.id
        ).delete()

        # 9. Store merged questions
        for idx, parsed in enumerate(merged_questions, start=1):
            q_num = idx
            question = Question(
                question_bank_id=question_bank.id,
                question_number=q_num,
                question_text=parsed["question_text"],
                marks=parsed["marks"],
                marks_source=parsed["marks_source"],
                repeat_count=parsed["repeat_count"],
                years_appeared=parsed["years_appeared"],
            )
            db.add(question)

        # 9. Mark extraction complete
        question_bank.status = "extracted"
        db.commit()
        db.refresh(question_bank)

        return len(parsed_questions)

    except HTTPException:
        question_bank.status = "uploaded"
        db.commit()
        raise

    except Exception:
        question_bank.status = "extraction_failed"
        db.commit()
        raise


def get_question_banks(db: Session, user_id: int | None = None) -> list[QuestionBank]:
    query = db.query(QuestionBank)
    if user_id is not None:
        query = query.filter(QuestionBank.user_id == user_id)

    return (
        query
        .order_by(QuestionBank.created_at.desc())
        .all()
    )


def get_question_bank(db: Session, question_bank_id: int) -> QuestionBank | None:
    return (
        db.query(QuestionBank)
        .filter(QuestionBank.id == question_bank_id)
        .first()
    )


def get_questions(db: Session, question_bank_id: int) -> list[Question]:
    return (
        db.query(Question)
        .filter(Question.question_bank_id == question_bank_id)
        .order_by(Question.question_number)
        .all()
    )


def add_question_to_bank(
    db: Session,
    question_bank_id: int,
    question_text: str,
    marks: int,
    question_number: int | None = None,
) -> Question:
    if question_number is None:
        last_question = (
            db.query(Question)
            .filter(Question.question_bank_id == question_bank_id)
            .order_by(Question.question_number.desc())
            .first()
        )
        question_number = (last_question.question_number + 1) if last_question else 1

    question = Question(
        question_bank_id=question_bank_id,
        question_number=question_number,
        question_text=question_text,
        marks=marks,
        marks_source="user_modified",
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    return question
