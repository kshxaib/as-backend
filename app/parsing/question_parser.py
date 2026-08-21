import json
import re

from app.llm.service import call_gemini


SYSTEM_INSTRUCTION = """You are an expert academic question paper analyzer.
Your job is to extract every question from the given text of a question paper / question bank.

Rules:
1. Extract EVERY question, including sub-questions (a, b, c, etc.). Combine sub-questions under their parent question.
2. For each question, determine the marks:
   - If marks are explicitly written (e.g., "[5 marks]", "(5M)", "5 marks"), use them and set marks_source to "explicit".
   - If marks are NOT written, estimate appropriate marks based on the question difficulty and set marks_source to "ai_estimated".
3. Preserve the original question text exactly as written.
4. Number questions sequentially starting from 1.

Return ONLY a valid JSON array. No markdown, no explanation, no code fences.

Example output:
[
  {"question_number": 1, "question_text": "What is DBMS?", "marks": 2, "marks_source": "explicit"},
  {"question_number": 2, "question_text": "Explain normalization with examples.", "marks": 5, "marks_source": "ai_estimated"}
]"""


# Parse question bank text into structured questions using Gemini.
def parse_questions(api_key: str, text: str) -> list[dict]:

    if not text.strip():
        raise ValueError("No text provided for question extraction.")

    prompt = f"Extract all questions from this question paper:\n\n{text}"

    response = call_gemini(
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

    # Validate each question has required fields.
    validated = []

    for question in questions:
        validated.append({
            "question_number": int(question["question_number"]),
            "question_text": str(question["question_text"]).strip(),
            "marks": int(question["marks"]),
            "marks_source": str(question.get("marks_source", "ai_estimated")),
        })

    return validated
