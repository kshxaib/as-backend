import json
import re

from app.llm.router import call_extraction


SYSTEM_INSTRUCTION = """You are an expert academic exam paper analyzer specializing in university and college examination papers.

Your ONLY job is to extract EVERY individual question or sub-question from the exam paper as a SEPARATE structured item in a JSON array.

=== CRITICAL: INDIVIDUAL QUESTION EXTRACTION ===

Exam papers often use GROUP HEADER patterns like:
  Q.1 for 2 Marks          ← This means ALL sub-questions under this header are worth exactly 2 Marks each
    a. Sub-question text   ← marks: 2, marks_source: "explicit"
    b. Sub-question text   ← marks: 2, marks_source: "explicit"
  Q.2 for 5 Marks          ← This means ALL sub-questions under this header are worth exactly 5 Marks each
    a. Sub-question text   ← marks: 5, marks_source: "explicit"
    b. Sub-question text   ← marks: 5, marks_source: "explicit"
  Q.3 for 10 Marks         ← This means ALL sub-questions under this header are worth exactly 10 Marks each
    a. Sub-question text   ← marks: 10, marks_source: "explicit"

You MUST extract EACH sub-question (a, b, c, d ...) as a SEPARATE question entry.
Do NOT group sub-questions under a single parent entry.

=== !! ABSOLUTE RULE FOR GROUP MARKS !! ===

When a GROUP HEADER like "Q.1 for 2 Marks" or "Q.2 for 5 Marks" is present:
  - ALL sub-questions under that group header MUST have marks = the group header value.
  - You are STRICTLY FORBIDDEN from using your own complexity judgment to change the marks value.
  - "List and explain fuzzification methods" under "Q.1 for 2 Marks" → marks: 2 NOT 5.
  - "Explain Markov decision process" under "Q.1 for 2 Marks" → marks: 2 NOT 5.
  - "Explain Bayes Theorem" under "Q.1 for 2 Marks" → marks: 2 NOT 5.
  - The group header ALWAYS overrides any complexity-based judgment.
  - Set marks_source: "explicit" for all questions in an explicitly marked group.

=== MARKS RESOLUTION & AI ESTIMATION RULES ===

1. EXPLICIT MARKS (when marks ARE clearly printed on the paper):
   - Group headers ("Q.1 for 2 Marks", "Section A - 2 marks each", marks table at top): ALL questions in that group get the group's mark value with marks_source: "explicit".
   - Per-question marks ("(2M)", "[5]", "5 Marks" next to a specific question): use exact value, marks_source: "explicit".

2. AI ESTIMATED MARKS (when NO marks are specified on the paper):
   - CRITICAL: If an exam paper DOES NOT explicitly state marks numbers anywhere, YOU MUST NOT mark them as 'explicit'. Set marks_source: "ai_estimated".
   - Estimate standard academic mark weight (2, 5, or 10) based on question complexity:
     * 2 Marks: Short definitions, short terms, state, list, identify, name, single formula.
     * 5 Marks: Medium explanations, comparisons, functional blocks, short notes, multi-step.
     * 10 Marks: Detailed architecture diagrams, comprehensive design, proofs, long essays.
   - ALWAYS output an integer for marks (2, 5, or 10). NEVER output 0, null, or string values.

=== EXTRACTION RULES ===

1. Each extracted item = ONE individual question/sub-question.
2. Number items sequentially: 1, 2, 3, 4, 5, 6, ... (global sequential ordering).
3. Preserve the full question text accurately without leading numbers/prefixes like "a.", "1.", "(i)".
4. Return ONLY a valid JSON array of objects. No markdown formatting, no code fences, no preamble text.

=== OUTPUT FORMAT ===

[
  {"question_number": 1, "question_text": "Perform Union intersection difference and complement over fuzzy sets", "marks": 2, "marks_source": "explicit"},
  {"question_number": 2, "question_text": "Explain Markov decision process in detail", "marks": 2, "marks_source": "explicit"},
  {"question_number": 3, "question_text": "Explain the elements present in a Cognitive system", "marks": 5, "marks_source": "explicit"}
]"""


def detect_paper_has_explicit_marks(text: str) -> bool:
    """
    Scans the entire PDF text for presence of genuine marks indicators.
    If no marks patterns exist anywhere in the paper, all extracted questions
    must have marks_source='ai_estimated'.
    """
    if not text:
        return False
    lower = text.lower()
    patterns = [
        r"\b(?:marks?|max\.?\s*marks?|maximum\s*marks?)\s*[:=]\s*\d+",
        r"\b\d{1,2}\s*(?:marks?|mark|m)\b",
        r"\[\s*\d{1,2}\s*(?:marks?|m)?\s*\]",
        r"\(\s*\d{1,2}\s*(?:marks?|m)\s*\)",
        r"section\s+[a-z0-9]\s*[-–:]\s*\d+\s*marks",
    ]
    for pat in patterns:
        if re.search(pat, lower):
            return True
    return False


def _clean_and_estimate_marks(
    raw_marks,
    question_text: str,
    raw_source: str | None,
    paper_has_explicit_marks: bool = True,
) -> tuple[int, str]:
    """
    Safely resolves marks to a standard academic mark tier (2, 5, 10).

    Key logic:
    - If paper has explicit marks AND LLM returned marks_source='explicit' with a valid
      positive integer → trust the LLM's value as-is (it correctly read the group header).
    - If paper has NO explicit marks → force 'ai_estimated' and estimate 2/5/10 locally.
    - If paper has explicit marks but LLM returned invalid/null marks → fall back to
      local AI estimation but keep 'ai_estimated' since we can't confirm the value.
    """
    parsed_val = None

    if isinstance(raw_marks, (int, float)):
        if int(raw_marks) > 0:
            parsed_val = int(raw_marks)
    elif isinstance(raw_marks, str) and raw_marks.strip():
        digits = re.findall(r"\d+", raw_marks)
        if digits and int(digits[0]) > 0:
            parsed_val = int(digits[0])

    # Paper has explicit marks AND LLM correctly set marks_source='explicit' with a valid value
    is_llm_explicit = (
        paper_has_explicit_marks
        and str(raw_source).strip().lower() == "explicit"
        and parsed_val is not None
    )
    if is_llm_explicit:
        return parsed_val, "explicit"

    # If paper has NO explicit marks → always AI estimate
    # If paper has explicit marks but LLM returned ai_estimated/null → also AI estimate
    # (LLM may have missed some edge cases; we do NOT blindly trust wrong LLM values)

    # AI Estimation: Normalize to standard tiers (2, 5, 10)
    lower = question_text.lower().strip()

    # 10 Marks (Heavy architecture, proofs, comprehensive system designs, 3-way hierarchies)
    if (
        any(k in lower for k in ["architecture", "in detail", "design", "prove", "derive", "comprehensive", "case study", "elaborate", "with diagram", "neat sketch", "hierarchy"]) or
        len(lower) > 160
    ):
        return 10, "ai_estimated"

    # 5 Marks (Medium explanations, comparisons, functional blocks, operations, multi-part concepts)
    if (
        any(k in lower for k in ["explain", "differentiate", "compare", "versus", " vs ", "vs.", "discuss", "describe", "illustrate", "short note", "algorithm", "evaluate", "step by step", "distinguish", "properties", "functional block", "stack", "operation", "devices", "application"]) or
        len(lower) >= 42
    ):
        return 5, "ai_estimated"

    # 2 Marks (Brief terms, short topics, definitions, formulas)
    return 2, "ai_estimated"



def parse_questions(text: str, user_keys: dict[str, str] | None = None) -> list[dict]:
    if not text.strip():
        raise ValueError("No text provided for question extraction.")

    paper_has_explicit_marks = detect_paper_has_explicit_marks(text)

    group_marks_rule = (
        "CRITICAL GROUP MARKS RULE: When the paper has group headers like 'Q.1 for 2 Marks' or "
        "'Q.2 for 5 Marks', every sub-question under that group MUST get exactly that mark value "
        "with marks_source='explicit'. DO NOT use question complexity to change the value. "
        "'Explain Markov decision process' under 'Q.1 for 2 Marks' → marks: 2, not 5. "
        "'List and explain fuzzification methods' under 'Q.1 for 2 Marks' → marks: 2, not 5."
    )

    prompt = (
        "Analyze this exam paper and extract EVERY question and sub-question as a SEPARATE row.\n\n"
        "RULES:\n"
        "1. Extract each sub-question individually, not grouped under the parent.\n"
        f"2. Paper explicit marks detection: {'EXPLICIT MARKS FOUND in paper - use exact group header marks with marks_source=explicit for ALL questions' if paper_has_explicit_marks else 'NO MARKS PRINTED IN PAPER - you MUST set marks_source=ai_estimated for ALL questions and estimate 2, 5, or 10 marks'}.\n"
        f"3. {group_marks_rule}\n"
        "4. Assign global sequential numbering (1, 2, 3, 4, 5...).\n\n"
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

    try:
        questions = json.loads(cleaned)
    except Exception as err:
        # Try extracting first JSON array if extra wrapper text exists
        array_match = re.search(r"\[\s*\{.*\}\s*\]", cleaned, re.DOTALL)
        if array_match:
            questions = json.loads(array_match.group(0))
        else:
            raise ValueError(f"LLM did not return a valid JSON array: {str(err)}")

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

        q_text = str(question.get("question_text", "")).strip()
        if not q_text:
            continue

        raw_marks = question.get("marks")
        raw_source = question.get("marks_source")

        marks_val, source_val = _clean_and_estimate_marks(
            raw_marks=raw_marks,
            question_text=q_text,
            raw_source=raw_source,
            paper_has_explicit_marks=paper_has_explicit_marks,
        )

        validated.append({
            "question_number": assigned_num,
            "question_text": q_text,
            "marks": marks_val,
            "marks_source": source_val,
        })

    return validated
