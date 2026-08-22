import json
import re

from app.llm.router import call_extraction


SYSTEM_INSTRUCTION = """You are an expert academic exam paper analyzer specializing in Indian university question papers.

Your ONLY job is to extract EVERY individual sub-question from the exam paper as a SEPARATE item.

=== CRITICAL: INDIVIDUAL SUB-QUESTION EXTRACTION ===

Indian exam papers use a pattern like:
  Q.1 for 2 Marks
    a. Sub-question text
    b. Sub-question text
    ...
  Q.2 for 5 Marks
    a. Sub-question text
    ...

You MUST extract EACH sub-question (a, b, c, d ...) as a SEPARATE question entry.
Do NOT group sub-questions under a single Q.1 or Q.2 entry.
The marks for each sub-question come from the parent Q.X line (e.g. "Q.1 for 2 Marks" → all sub-questions under Q.1 get 2 marks).

=== MARKS RESOLUTION ===

Marks can appear as:
- "Q.1 for 2 Marks" → all sub-questions under Q.1 get marks = 2
- "(2M)" or "(5M)" or "[2]" or "2 Marks" inline with the question
- A marks table at the top listing each question's marks
- Section headers like "Section A - 2 marks each"
- Mark columns on the right side of the paper

marks_source values:
- "explicit" — marks clearly stated in the paper
- "ai_estimated" — marks guessed (use ONLY if no marks info exists anywhere)

=== EXTRACTION RULES ===

1. Each extracted item = ONE sub-question (a, b, c...), NOT the parent Q.X group.
2. Number items sequentially: 1, 2, 3, 4, 5, 6, ... (global sequential, not per-section).
3. Preserve the original sub-question text exactly as written (without the leading "a.", "b." prefix).
4. If a question has no sub-questions (just a standalone question), extract it as one item.
5. Return ONLY a valid JSON array. No markdown, no code fences, no explanation.

=== OUTPUT FORMAT ===

[
  {"question_number": 1, "question_text": "Perform Union, intersection, difference and complement over the fuzzy sets", "marks": 2, "marks_source": "explicit"},
  {"question_number": 2, "question_text": "Perform algebraic sum, algebraic product, bounded sum and bounded difference on fuzzy sets", "marks": 2, "marks_source": "explicit"},
  {"question_number": 3, "question_text": "List and explain fuzzification methods (membership methods)", "marks": 2, "marks_source": "explicit"},
  {"question_number": 4, "question_text": "Explain the elements present in a Cognitive system", "marks": 5, "marks_source": "explicit"}
]"""


def parse_questions(text: str, user_keys: dict[str, str] | None = None) -> list[dict]:
    if not text.strip():
        raise ValueError("No text provided for question extraction.")

    prompt = (
        "Carefully analyze this exam paper. Extract EACH individual sub-question (a, b, c...) as a SEPARATE entry.\n\n"
        "IMPORTANT RULES:\n"
        "1. Do NOT group all sub-questions under Q.1 as one item — each sub-question is its own row.\n"
        "2. Each sub-question inherits its marks from the parent Q.X heading "
        "(e.g. if Q.1 says '2 Marks', all sub-questions a, b, c under Q.1 each get marks=2).\n"
        "3. Give each extracted sub-question a UNIQUE sequential number: 1, 2, 3, 4, 5, ...\n"
        "4. First scan the entire paper for any marks table, section headers, or marks columns. "
        "These define EXPLICIT marks even if individual questions don't repeat the marks inline.\n\n"
        "Exam paper text:\n\n"
        f"{text}"
    )

    response = call_extraction(
        prompt=prompt,
        system_instruction=SYSTEM_INSTRUCTION,
        user_keys=user_keys,
        task_name="Question Bank PDF Extraction",
    )

    cleaned = response.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    questions = json.loads(cleaned)

    if not isinstance(questions, list):
        raise ValueError("LLM did not return a valid JSON array.")

    raw_nums = [q.get("question_number") for q in questions if isinstance(q, dict)]
    has_duplicate_nums = len(raw_nums) != len(set(raw_nums))

    validated = []

    for idx, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue

        q_num = question.get("question_number")
        if has_duplicate_nums or not isinstance(q_num, int) or q_num <= 0:
            assigned_num = idx
        else:
            assigned_num = q_num

        validated.append({
            "question_number": assigned_num,
            "question_text": str(question.get("question_text", "")).strip(),
            "marks": int(question.get("marks", 2)),
            "marks_source": str(question.get("marks_source", "ai_estimated")),
        })

    return validated
