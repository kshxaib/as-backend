"""
Service for AI-powered multi-paper pattern analysis and authentic predicted question paper synthesis.
"""

import json
import logging
import re
import pymupdf as fitz
from sqlalchemy.orm import Session

from app.db.models import QuestionBank, Question
from app.llm.router import call_openai_with_fallback, OPENAI_GENERATION_MODELS

logger = logging.getLogger("academicstack.predictor")

SYSTEM_PROMPT = """You are an elite academic professor, board curriculum designer, and chief examination paper setter for top universities.
You are given past examination papers for an academic subject spanning multiple semesters, sessions, or academic years.

Your objective is to perform a rigorous multi-year structural and conceptual trend analysis, then synthesize a BRAND NEW, 100% AUTHENTIC PREDICTED QUESTION PAPER matching that university's EXACT format, layout, and mark distribution.

=== STEP 1: DEEP EXAM PATTERN RECONSTRUCTION ===
Carefully examine all provided past papers to deduce:
1. Overall Marks & Time Allowance (e.g., 70 Marks / 3 Hours, 80 Marks, or 100 Marks).
2. Exact Section Division:
   - Does it have SECTION A, SECTION B, SECTION C?
   - Or Q.1 compulsory and answer any 3 out of Q.2-Q.6?
   - What are the marks per question (e.g., 2 Marks, 5 Marks, 10 Marks, 14 Marks)?
   - Are there sub-questions like 1(a), 1(b) or internal choices ("OR")?
3. Standard Instructions given to students (e.g. "Answer all questions from Section A", "Assume suitable data").

=== STEP 2: MULTI-YEAR TOPIC RECURRENCE & PREDICTION ===
Analyze the topic cadence across the uploaded papers:
1. Which core foundational concepts appear repeatedly across almost every paper? (Highest prediction weight).
2. Which concepts are cyclical (appeared 2 years ago, due to reappear now)?
3. What is the university's characteristic tone, problem style, and numerical-to-theory ratio?

=== STEP 3: PREDICTED QUESTION PAPER SYNTHESIS ===
Synthesize a brand new, highly realistic examination paper that mirrors the real exam:
- Formulate high-probability questions matching that exact format.
- DO NOT generate answers. Only synthesize the Question Paper!
- Ensure marks per section and total maximum marks sum accurately to the university standard.
- Assign an estimated prediction likelihood (e.g., "95%", "85%", "75%") based on recurrence trends.

=== OUTPUT FORMAT (STRICT JSON ONLY) ===
Output ONLY a valid, parseable JSON object matching this schema (no markdown fences, no commentary):
{
  "exam_meta": {
    "university_heading": "ACADEMICSTACK PREDICTED MODEL EXAMINATION",
    "subject": "<Subject Name>",
    "paper_title": "<Exam Title, e.g. Predicted Final Examination 2026>",
    "time_allowed": "3 Hours",
    "maximum_marks": 70,
    "general_instructions": [
      "Answer all questions from Section A.",
      "Figures to the right indicate full marks.",
      "Assume suitable data wherever necessary."
    ]
  },
  "pattern_insights": {
    "detected_format": "Detailed note on detected format (e.g., 3-Section layout with 10M Section A and 60M Sections B & C)",
    "recurring_topics": ["Topic 1", "Topic 2", "Topic 3"],
    "analysis_summary": "Brief 2-sentence rationale of how the multi-year trends were used to forecast this paper."
  },
  "sections": [
    {
      "section_name": "SECTION A",
      "section_instruction": "Answer all questions. (5 × 2 = 10 Marks)",
      "total_marks": 10,
      "questions": [
        {
          "question_number": "1(a)",
          "question_text": "State the difference between...",
          "marks": 2,
          "prediction_likelihood": "95%",
          "source_trend": "Repeated across multiple sessions",
          "is_or_choice": false
        }
      ]
    }
  ]
}
"""


def extract_text_from_pdf_bytes(file_bytes: bytes, filename: str = "Paper.pdf") -> str:
    """Extracts raw text from PDF bytes using PyMuPDF."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if text:
                pages.append(f"--- Page {page_num + 1} ---\n{text}")
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        logger.warning(f"Could not extract text from {filename}: {e}")
        return ""


def clean_json_response(raw_text: str) -> dict:
    """Extracts and parses JSON object from LLM response safely."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: attempt to find outermost braces
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("Failed to parse valid JSON from AI prediction model.")


def analyze_and_predict_paper(
    subject: str,
    title: str,
    papers: list[dict],
    user_keys: dict[str, str] | None = None,
) -> dict:
    """
    Analyzes multiple past papers and synthesizes a predicted question paper.
    papers: list of {'session': str, 'filename': str, 'text': str}
    """
    if not papers:
        raise ValueError("At least one past examination paper is required for analysis.")

    # Construct the prompt with all past paper transcripts
    prompt_sections = [
        f"TARGET SUBJECT: {subject}",
        f"TARGET PREDICTED TITLE: {title}",
        f"NUMBER OF PAST PAPERS PROVIDED: {len(papers)}",
        "\n=================== PAST EXAMINATION PAPERS CORPUS ===================",
    ]

    for idx, p in enumerate(papers, 1):
        session_label = p.get("session") or f"Paper #{idx}"
        filename = p.get("filename", "Unknown File")
        raw_text = p.get("text", "").strip()

        # Truncate each individual paper text if exceptionally long to prevent token overflow
        truncated_text = raw_text[:18000] if len(raw_text) > 18000 else raw_text

        prompt_sections.append(
            f"\n--- [PAST PAPER #{idx}] Session/Year: {session_label} (File: {filename}) ---\n"
            f"{truncated_text}\n"
            f"--- END OF PAST PAPER #{idx} ---\n"
        )

    prompt_sections.append(
        "\n=================== INSTRUCTIONS FOR PREDICTION ===================\n"
        "Carefully analyze all of the above past papers. Determine the exact university examination blueprint, "
        "time limits, sections, sub-question numbering, and mark distribution. Then formulate the high-probability "
        "Predicted Model Question Paper for this upcoming exam. Return STRICT JSON matching the specified schema."
    )

    full_prompt = "\n".join(prompt_sections)

    raw_response = call_openai_with_fallback(
        prompt=full_prompt,
        system_instruction=SYSTEM_PROMPT,
        user_keys=user_keys,
        candidate_models=OPENAI_GENERATION_MODELS,
        temperature=0.25,
        task_name="Multi-Paper Pattern Synthesis",
    )

    parsed_paper = clean_json_response(raw_response)
    
    # Ensure baseline structures exist
    if "exam_meta" not in parsed_paper:
        parsed_paper["exam_meta"] = {}
    parsed_paper["exam_meta"].setdefault("subject", subject)
    parsed_paper["exam_meta"].setdefault("paper_title", title)
    
    return parsed_paper


def save_predicted_paper_as_question_bank(
    db: Session,
    user_id: int,
    paper_data: dict,
) -> QuestionBank:
    """
    Saves the predicted paper as a QuestionBank and creates Question rows,
    enabling students to audit it or generate grounded solutions.
    """
    meta = paper_data.get("exam_meta", {})
    sections = paper_data.get("sections", [])
    subject = meta.get("subject", "Predicted Subject")
    title = meta.get("paper_title", "Predicted Examination Paper")

    # Create QuestionBank record
    qb = QuestionBank(
        user_id=user_id,
        name=title,
        subject=subject,
        cloudinary_url="",
        cloudinary_public_id="",
        files_meta=json.dumps([{
            "filename": f"{title.replace(' ', '_')}.pdf",
            "url": "",
            "public_id": "",
        }]),
        resource_ids="",
        status="extracted",
    )
    db.add(qb)
    db.commit()
    db.refresh(qb)

    # Flatten sections into individual question entries
    q_counter = 1
    for sec in sections:
        sec_name = sec.get("section_name", "Section")
        for q in sec.get("questions", []):
            if q.get("is_or_choice"):
                continue

            q_num_label = q.get("question_number", f"Q{q_counter}")
            q_text = q.get("question_text", "").strip()
            if not q_text:
                continue

            # Prefix with section name for editorial clarity
            full_text = f"[{sec_name}] {q_num_label}: {q_text}"
            raw_marks = q.get("marks", 5)
            try:
                marks_int = int(re.search(r"\d+", str(raw_marks)).group(0))
            except Exception:
                marks_int = 5

            db_q = Question(
                question_bank_id=qb.id,
                question_number=q_counter,
                question_text=full_text,
                marks=marks_int,
                marks_source="ai_estimated",
                repeat_count=2 if "high" in str(q.get("prediction_likelihood", "")).lower() else 1,
                years_appeared=q.get("source_trend", "Multi-Year Predicted"),
            )
            db.add(db_q)
            q_counter += 1

    db.commit()
    return qb
