"""
Service for AI-powered multi-paper pattern analysis and authentic predicted question paper synthesis.
Performs dynamic, zero-assumption blueprint extraction from uploaded past examination papers.
"""

import json
import logging
import re
import pymupdf as fitz
from sqlalchemy.orm import Session

from app.db.models import QuestionBank, Question
from app.llm.router import call_openai_with_fallback, OPENAI_GENERATION_MODELS

logger = logging.getLogger("academicstack.predictor")

SYSTEM_PROMPT = """You are an elite academic professor, university examination board chair, and senior question paper setter.
You are given authentic past examination papers for an academic course spanning multiple examination sessions.

Your mission is twofold:
1. Conduct a deep structural, question-by-question blueprint audit of the uploaded past examination papers.
2. Synthesize a 100% AUTHENTIC PREDICTED QUESTION PAPER strictly mirroring the exact blueprint, question hierarchy, sub-problems, and mark allocation discovered in the uploaded papers.

======================================================================
CRITICAL PRINCIPLE: ZERO PREDEFINED OR HARDCODED TEMPLATES
======================================================================
THERE IS NO FIXED OR PREDEFINED QUESTION PAPER FORMAT!
You MUST NOT assume:
- Do NOT assume Q.1 always has 6 sub-questions (it could have 4, 5, 6, 7, etc. depending on the paper).
- Do NOT assume Q.2 to Q.6 always have 2 sub-questions of 10 marks (some questions may have 2 sub-questions of 10M, some may have 3 sub-questions of 10M+5M+5M or 8M+6M+6M, some may have sub-parts like a(i) and a(ii), some may be short notes with 4 choices, etc.).
- Do NOT invent artificial sections like "SECTION A / B / C" if the past papers do not use them.

Instead, you must DISCOVER the authentic blueprint from the provided past papers through the following two-phase process:

----------------------------------------------------------------------
PHASE 1: DYNAMIC BLUEPRINT AUDIT (EXAMINE THE UPLOADED PAPERS)
----------------------------------------------------------------------
Inspect all uploaded papers and extract their exact anatomy:
1. Overall Exam Metadata:
   - What is the course/subject code and title?
   - What is the exact Duration / Time Allowed (e.g. 03 Hours, 3 Hours, 2.5 Hours)?
   - What is the exact Maximum Marks (e.g. 80, 70, 100, 60)?
   - What are the exact candidate instructions/notes (e.g. "Question No. 1 is compulsory", "Attempt any three questions out of remaining five", "Assume suitable data", etc.)?

2. Question-by-Question Blueprint:
   - How many main questions are there? (e.g. Q.1 to Q.6, or Q.1 to Q.5, or Part A/B).
   - For EACH main question, examine its exact structure:
     * Header & Instruction: e.g. "Q.1 Answer the following (Any four) — 05 marks each", or "Q.2 [20 Marks]", or "Q.6 Write short notes on any four".
     * Total marks for this main question.
     * Exact Sub-Questions:
       - Count how many sub-questions are provided in the real paper.
       - Note their labels (e.g. "a.", "b.", "c.", or "a.(i)", "a.(ii)", or "1.", "2.").
       - Note their individual marks (e.g. 5, 10, 6, 8, 4).
       - Note any nested sub-problems (e.g. a(i) [5M], a(ii) [5M]).

----------------------------------------------------------------------
PHASE 2: PREDICTED QUESTION PAPER SYNTHESIS
----------------------------------------------------------------------
Using the exact blueprint audited in Phase 1:
1. Replicate the EXACT number of main questions observed in the papers.
2. For every main question, replicate its EXACT number of sub-questions and mark distribution:
   - If Q.1 in the papers gives 5 sub-questions (a to e), generate all 5 sub-questions. If it gives 6 (a to f), generate all 6 sub-questions.
   - If Q.2 has 2 sub-questions (a [10], b [10]), generate 2 sub-questions.
   - If Q.3 has 3 sub-questions (a [10], b [5], c [5]), generate all 3 sub-questions with those exact marks.
   - If a question has sub-parts like a.(i) and a.(ii), represent them faithfully with their respective marks.
   - If Q.6 is a short notes question with 5 options to answer any 4, generate all 5 options.
3. Formulate high-probability questions matching the university's characteristic tone, style, and syllabus coverage based on past paper recurrence.
4. DO NOT generate answers. Only synthesize the examination paper.

======================================================================
CRITICAL: THE "CHOICE QUESTIONS" MANDATORY POOL RULE
======================================================================
When a question instruction specifies a choice:
- "Answer the following (Any four) — 05 marks each"
  * In the uploaded past papers, Q.1 provides SIX sub-questions: a, b, c, d, e, f!
  * DO NOT GENERATE ONLY 4 SUB-QUESTIONS! If you output only 4, the student has NO choice!
  * You MUST generate ALL 6 sub-questions (a, b, c, d, e, f) in the "questions" array for Q.1!
- "Attempt any three questions out of remaining five questions"
  * Generate ALL remaining questions (e.g. Q.2, Q.3, Q.4, Q.5, Q.6) completely!
- "Write short notes on any four"
  * If the past paper provides 5 or 6 options, generate ALL 5 or 6 options!

======================================================================
OUTPUT FORMAT (STRICT JSON ONLY, NO MARKDOWN, NO COMMENTARY)
======================================================================
{
  "exam_meta": {
    "university_heading": "<e.g. UNIVERSITY OF MUMBAI • MODEL EXAMINATION or university name from paper>",
    "subject": "<Subject Name from papers>",
    "paper_title": "<Exam Title, e.g. BE SEM-VII Examination>",
    "time_allowed": "<e.g. 03 Hours>",
    "maximum_marks": <Integer, e.g. 80>,
    "general_instructions": [
      "<Instruction 1 from paper>",
      "<Instruction 2 from paper>",
      "<Instruction 3 from paper>"
    ]
  },
  "pattern_insights": {
    "detected_format": "<Describe the exact blueprint discovered from the past papers: e.g. Q.1 has N sub-questions of X marks each; Q.2 to Q.6 question and mark breakdown; total marks and time allowance.>",
    "recurring_topics": ["<Core Topic 1>", "<Core Topic 2>", "<Core Topic 3>", "<Core Topic 4>", "<Core Topic 5>"],
    "analysis_summary": "<2-3 sentence analysis of syllabus coverage, question cadence, and high-yield concepts detected across papers.>"
  },
  "sections": [
    {
      "section_name": "<Main Question label, e.g. Q.1 or Q.1 Answer the following>",
      "section_instruction": "<Instruction for this question, e.g. Answer any four (05 marks each) or [20 Marks]>",
      "total_marks": <Total marks for this question, e.g. 20>,
      "questions": [
        {
          "question_number": "<Sub-question label matching paper, e.g. a. or a.(i) or 1(a)>",
          "question_text": "<Predicted question text>",
          "marks": <Integer marks for this sub-question, e.g. 5 or 10 or 6>,
          "prediction_likelihood": "<e.g. 95% or 90% or 85%>",
          "source_trend": "<e.g. Repeated across multiple sessions or Core recurring concept>",
          "is_or_choice": false
        }
      ]
    }
  ]
}
"""


from app.llm.router import call_openai_with_fallback, OPENAI_GENERATION_MODELS, transcribe_image_with_vision


def _is_readable_text(text: str) -> bool:
    """Checks if extracted text is legible English content rather than empty or unmapped font glyphs."""
    alnum_count = sum(1 for c in text if c.isalnum())
    if alnum_count < 30:
        return False
    vowels = sum(1 for c in text.lower() if c in "aeiou")
    if vowels < 8:
        return False
    return True


def extract_text_from_pdf_bytes(
    file_bytes: bytes,
    filename: str = "Paper.pdf",
    user_keys: dict[str, str] | None = None,
) -> str:
    """
    Extracts raw text from PDF bytes using PyMuPDF.
    Uses block-level extraction and filters out repetitive watermark strings (e.g. repeated stamps).
    If a page has no readable text (e.g. scanned photocopy or unmapped font glyphs like QB 7),
    it automatically falls back to OpenAI Vision to transcribe the page questions accurately.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("blocks")
            clean_blocks = []
            for b in blocks:
                b_text = b[4].strip()
                if not b_text:
                    continue
                # Clean repetitive watermark strings (e.g. A464X525YCFA464X525YCF repeated tokens)
                lines = [l.strip() for l in b_text.splitlines() if l.strip()]
                filtered = [l for l in lines if not re.search(r'([A-Za-z0-9]{3,15})\1{2,}', l)]
                if filtered:
                    clean_blocks.append("\n".join(filtered))

            page_content = "\n\n".join(clean_blocks).strip()
            
            # Fallback to standard text extraction if block filtering was too aggressive
            if not _is_readable_text(page_content):
                raw_text = page.get_text("text").strip()
                if _is_readable_text(raw_text):
                    page_content = raw_text

            # Vision OCR fallback if text is still unreadable (e.g. scanned or unmapped font glyphs)
            if not _is_readable_text(page_content) and user_keys and user_keys.get("openai"):
                try:
                    logger.info(f"Page {page_num + 1} of {filename} has unreadable text encoding. Invoking Vision OCR fallback...")
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    vision_text = transcribe_image_with_vision(image_bytes=img_bytes, user_keys=user_keys)
                    if vision_text.strip():
                        page_content = vision_text.strip()
                        logger.info(f"Vision OCR successfully transcribed {len(page_content)} characters for page {page_num + 1}")
                except Exception as ve:
                    logger.warning(f"Vision OCR fallback failed for page {page_num + 1} of {filename}: {ve}")

            if page_content.strip():
                pages.append(f"--- Page {page_num + 1} ---\n{page_content}")

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
    Analyzes multiple past papers and dynamically extracts the authentic blueprint
    without any predefined question counts or rigid assumptions.
    """
    if not papers:
        raise ValueError("At least one past examination paper is required for analysis.")

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

        truncated_text = raw_text[:18000] if len(raw_text) > 18000 else raw_text

        prompt_sections.append(
            f"\n--- [PAST PAPER #{idx}] Session/Year: {session_label} (File: {filename}) ---\n"
            f"{truncated_text}\n"
            f"--- END OF PAST PAPER #{idx} ---\n"
        )

    prompt_sections.append(
        "\n=================== CRITICAL BLUEPRINT REPLICATION INSTRUCTIONS ===================\n"
        "1. NO PREDEFINED ASSUMPTIONS: Read the past papers above carefully. Do NOT assume any fixed number of questions or sub-questions! "
        "Count the actual main questions and inspect how each question is subdivided in the uploaded papers.\n"
        "2. ACCURATE SUB-QUESTION COUNTS & FULL CHOICE POOL (DO NOT STOP AT 4!):\n"
        "- For Q.1: In the uploaded past paper, Q.1 lists 6 sub-questions (a, b, c, d, e, f) for students to choose 'Any four'. "
        "You MUST generate ALL 6 sub-questions (a, b, c, d, e, f) with 5 marks each! DO NOT output only 4 questions! If you only output 4, there is no choice for the student.\n"
        "- For Q.2, Q.3, Q.4, Q.5, Q.6: Generate ALL of them completely. Do not assume 2 sub-questions of 10 marks for everything. "
        "If a question has 2 parts, generate 2 parts. If a question has 3 parts (e.g. 10M + 5M + 5M), generate 3 parts. "
        "If a question has nested sub-items like a(i) and a(ii), generate them accurately. "
        "If a short-notes question has 5 options to answer any 4, generate all 5 options.\n"
        "- Generate the complete examination paper matching that exact blueprint.\n"
        "3. EXAM METADATA: Match the exact Duration, Maximum Marks, and candidate notes from the uploaded papers.\n"
        "4. ONLY QUESTIONS: Generate only the examination paper. Do not include answers.\n"
        "Return STRICT JSON only matching the schema."
    )

    full_prompt = "\n".join(prompt_sections)

    raw_response = call_openai_with_fallback(
        prompt=full_prompt,
        system_instruction=SYSTEM_PROMPT,
        user_keys=user_keys,
        candidate_models=OPENAI_GENERATION_MODELS,
        temperature=0.25,
        task_name="Dynamic Exam Blueprint Synthesis",
    )

    parsed_paper = clean_json_response(raw_response)
    
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
    Saves the predicted paper as a QuestionBank and creates Question rows.
    """
    meta = paper_data.get("exam_meta", {})
    sections = paper_data.get("sections", [])
    subject = meta.get("subject", "Predicted Subject")
    title = meta.get("paper_title", "Predicted Examination Paper")

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

            full_text = f"[{sec_name} {q_num_label}] {q_text}"
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
