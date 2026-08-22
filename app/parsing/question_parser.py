import json
import re

from app.llm.service import call_openai


SYSTEM_INSTRUCTION = """You are an expert academic exam paper analyzer specializing in Indian university question papers.

Your ONLY job is to extract every question and its marks from the given exam paper text.

=== CRITICAL: SEQUENTIAL QUESTION NUMBERING ===
1. Each extracted question MUST have a UNIQUE, sequential integer `question_number` starting from 1 (1, 2, 3, 4, 5, ...).
2. DO NOT output the same `question_number` for all items. Each question MUST increment (e.g. Q1, Q2, Q3, etc.).
3. If the paper has multiple sections (e.g. Section A has 10 questions, Section B has 10 questions), continue numbering sequentially (1 to 20+).

=== CRITICAL: HOW TO FIND MARKS ===

Indian university exam papers express marks in these common patterns — you MUST recognize ALL of them:

EXPLICIT marks patterns (marks_source = "explicit"):
- "(2M)" or "(5M)" or "(10M)" — marks in parentheses with M suffix
- "[2]" or "[5]" or "[10]" — marks in square brackets  
- "2 Marks" or "5 Marks" or "10 Marks" — written out
- "2M" or "5M" or "10M" — marks with M suffix (no brackets)
- "(02)" or "(05)" or "(10)" — marks as zero-padded numbers in brackets
- "Q1 (5)" or similar — marks after question reference
- A marks table or column at the start/end of the paper listing each question's marks
- "Unit" or "Section" headers that specify all questions in that section carry X marks (e.g., "Section A - Answer all questions (2 Marks each)")

IMPORTANT: In many Indian exam papers, marks are listed in a TABLE at the top or as a column on the right side. 
Even if a question's inline text doesn't have "(5M)", if the table or section header says questions carry 2 or 5 marks, use that with marks_source = "explicit".

AI Estimated (marks_source = "ai_estimated"):
- Only when the paper has absolutely NO marks information anywhere, not even a table or section header.

=== EXTRACTION RULES ===

1. Extract EVERY question. Combine sub-questions (e.g. 1a, 1b) under their parent question if related, or make them distinct sequential items.
2. Number questions sequentially: 1, 2, 3, 4, 5, 6, ...
3. Preserve the original question text exactly as written.
4. Return ONLY a valid JSON array. No markdown, no explanation, no code fences.

=== OUTPUT FORMAT ===

[
  {"question_number": 1, "question_text": "Perform Union, intersection, difference and complement over the fuzzy sets", "marks": 2, "marks_source": "explicit"},
  {"question_number": 2, "question_text": "Perform algebraic sum, algebraic product, bounded sum and bounded difference on fuzzy sets", "marks": 2, "marks_source": "explicit"},
  {"question_number": 3, "question_text": "List and explain fuzzification methods", "marks": 2, "marks_source": "explicit"}
]"""


# Parse question bank text into structured questions using OpenAI.
def parse_questions(api_key: str, text: str) -> list[dict]:

    if not text.strip():
        raise ValueError("No text provided for question extraction.")

    prompt = (
        "Carefully analyze this exam paper and extract all questions with their marks.\n\n"
        "IMPORTANT RULES:\n"
        "1. Give each question a UNIQUE sequential number: 1, 2, 3, 4, 5, ... (DO NOT set question_number=1 for all questions).\n"
        "2. First scan the entire paper for any marks table, section headers like "
        "'Section A – 2 marks each', or marks columns on the right side. "
        "These define EXPLICIT marks even if individual questions don't repeat the marks inline.\n\n"
        "Exam paper text:\n\n"
        f"{text}"
    )

    response = call_openai(
        api_key=api_key,
        prompt=prompt,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    # Clean the response — strip code fences if the LLM adds them.
    cleaned = response.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    questions = json.loads(cleaned)

    if not isinstance(questions, list):
        raise ValueError("LLM did not return a valid JSON array.")

    # Validate and strictly enforce sequential 1-based numbering
    # Check if duplicate numbers exist (e.g. all 1s)
    raw_nums = [q.get("question_number") for q in questions if isinstance(q, dict)]
    has_duplicate_nums = len(raw_nums) != len(set(raw_nums))

    validated = []

    for idx, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            continue

        q_num = question.get("question_number")
        # If numbers had duplicates or were missing, renumber sequentially 1..N
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
