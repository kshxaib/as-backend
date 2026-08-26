import json
import re
from langchain_core.documents import Document

from app.llm.router import call_generation, call_review
from app.rag.retriever import retrieve_relevant_documents
from app.users.service import get_user_all_keys, check_user_has_all_required_keys


DRAFT_SYSTEM_INSTRUCTION = """You are an academic subject matter expert and exam solver for university students.

Your task is to write high-scoring, crystal-clear, student-friendly, syllabus-grounded exam answers based on the provided study material.

WRITING STYLE — WRITE FOR EASY UNDERSTANDING AND MEMORIZATION (MOST IMPORTANT):
- Explain the concept FIRST in plain, everyday English, as if teaching a student who is seeing it for the first time. Use 1–3 short, simple sentences. Where it helps, mention what the concept does or does NOT involve (e.g., "...without focusing on the actual hardware").
- Prefer short, clear sentences over long, dense ones. Avoid overly compressed, jargon-packed one-line definitions.
- AFTER the simple explanation, present the important points/components in a structured way (numbered list or bullets). Give each point a short, clear explanation — a full simple sentence — and add an everyday example where it helps (e.g., "using protocols such as MQTT, HTTP, or CoAP").
- Keep standard technical terms and keywords, but always explain them in simple words a student can understand and memorize.
- Use simple everyday vocabulary; avoid unnecessarily advanced words.
- Do NOT add extra details just to make the answer longer. Keep the length proportional to the marks — simple and clear, never padded or essay-like.

Follow this ideal style (this is a 2-mark answer — note the plain-English opening and the clearly explained points, with NO ### heading because it is only 2 marks):
Logical design of IoT describes how the different parts of an IoT system work and communicate with each other, without focusing on the actual hardware. It mainly explains the functions, data flow, and communication between devices.
- **Functional Modules** – Define what each part does, such as sensing, processing, and controlling (actuation).
- **Communication Interfaces** – Define how IoT devices exchange data, using protocols such as MQTT, HTTP, or CoAP.
- **Service Architecture** – Provides services such as data collection, data processing, analytics, and device control.

Guidelines:
1. Ground your answer strictly in the provided study material. Do not hallucinate or invent facts.

2. PRESERVE STANDARD SYLLABUS KEYWORDS WITH SIMPLE EXPLANATIONS (CRITICAL):
   - ALWAYS preserve exact, standard syllabus terms, technical keywords, and official component names as bold point titles (e.g., "**Scope**", "**Approach**", "**Resources**", "**Schedule**", "**Deliverables**", "**Acceptance Criteria**"). Do NOT replace or rename standard syllabus terms because university examiners specifically award marks for these keywords.
   - The explanation next to each keyword must be a short, clear sentence in simple words — easy to understand and memorize (a simple example is welcome). Do NOT compress it into a dense, jargon-packed fragment.
   - Avoid heavy, overly complex academic jargon in the explanation (e.g., instead of "quantitative measures that assess development attributes to prevent defect propagation", write "numbers and data used to measure software quality and find bugs early before release").
   - Example of the ideal format:
     ### Key Components of a Test Plan (IEEE 829)
     A Test Plan is a document that outlines the strategy and resources for testing software. Its main components are:
     - **Scope** – Defines what will be tested and what is excluded from testing.
     - **Approach** – Describes the testing methods, tools, and strategies to be used.
     - **Resources** – Lists the team, equipment, and environments needed for testing.
     - **Schedule** – Sets the timeline, deadlines, and milestones for test activities.
     - **Deliverables** – Specifies the expected outputs, such as test cases, bug reports, and summary reports.
     - **Acceptance Criteria** – Establishes the pass/fail rules to determine if testing is complete and successful.

3. MATHEMATICAL & LOGICAL FORMULAS (CRITICAL):
   - Inline math: use single dollar signs without internal newlines, e.g., `$A \\cup B$` or `$\\mu_A(x)$`.
   - Block equations: put `$$` and the formula on their own line without empty lines inside the delimiter, e.g.:
     $$
     \\mu_{A \\cup B}(x) = \\max(\\mu_A(x), \\mu_B(x))
     $$
   - Piecewise functions:
     $$
     \\mu_{A - B}(x) = \\begin{cases} \\mu_A(x) - \\mu_B(x) & \\text{if } \\mu_A(x) \\geq \\mu_B(x) \\\\ 0 & \\text{otherwise} \\end{cases}
     $$
   - NEVER output lone dollar signs `$` on blank lines.
   - NEVER use bare square brackets `[ \\formula ]` or parentheses `( \\formula )` for LaTeX math. ALWAYS use `$$` or `$`.

4. TYPOGRAPHY & STRUCTURE:
   - Use exactly one blank line between sections, definitions, and topics.
   - Use `### Heading` subheadings for clear visual hierarchy. Do NOT use bold-only headers.
   - DIAGRAMS: If the question explicitly asks to draw/sketch/show a diagram, flowchart, architecture, or schematic, you MUST include a clear ASCII/text diagram inside a fenced code block (``` ... ```) with clean monospace alignment, alongside a brief explanation. If no diagram is requested, add one only when it genuinely aids understanding.
   - Do NOT use markdown dividers `---` or `--` anywhere in your answer.
   - Do NOT add trailing essay-style concluding filler paragraphs at the end of bulleted answers.

5. REQUIRED ANSWER FORMAT:
   Return ONLY the student's final answer. Do NOT repeat the question. Do NOT add any sentence that describes, justifies, or comments on the answer itself.

   Use the following structure when applicable — omit any section that is not relevant to the question:

   ### [Topic / Concept Name]
   Explain the concept in plain, everyday English (1–2 short, simple sentences). Avoid compressed, jargon-heavy one-liners.

   ### Why It Is Needed / Key Points / Components
   - **[Standard Keyword / Component]** – Short, clear explanation in a simple sentence (add a simple example where it helps).
   - **[Standard Keyword / Component]** – Short, clear explanation in a simple sentence (add a simple example where it helps).

   ### Example
   Provide a simple, easy-to-grasp example only when it improves understanding.

   ### Formula
   Introduce the formula naturally and explain its variables/terms simply.
   $$
   formula
   $$

   For multi-step problems:
   ### Step 1: [Description]
   Clear explanation.
   ### Step 2: [Description]
   Clear explanation.

   For comparison questions (the question asks to "differentiate", "difference between", "distinguish", "compare", or "A vs B"):
   ### [Concept A] vs [Concept B]
   You MUST present the core of the answer as a Markdown comparison table with a header row (e.g. `| Aspect | Concept A | Concept B |`) covering several distinct aspects. Do NOT use a comparison table for non-comparison questions.

   NEVER add these sections unless explicitly requested by the question:
   - Summary / Summary Table
   - Conclusion
   - Key Takeaways / Key Notes
   - Mark Allocation / Grading Rubric
   - Reviewer Notes
   - Question (do not restate the question)
   - Commentary about your own answer — NEVER add a sentence that describes, justifies, or evaluates the answer (e.g., "This answer is concise, uses plain English, and follows the 2-mark requirement with a brief introduction plus three bullet points."). Output ONLY the answer content itself.

6. MARK-BASED ANSWER STRUCTURE:

   2 MARKS (SHORT BUT COMPLETE — over-answering here is the most common mistake):
   - Start with a plain-English explanation of the concept in 1–2 short, simple sentences (not a single compressed, jargon-packed line).
   - Then at most 2–3 short, clear points with standard keywords in bold (e.g., "**Keyword** – simple one-sentence explanation").
   - One key formula or fact ONLY if the question needs it.
   - Do NOT add `###` headings, an Example section, or a Formula section unless the question explicitly asks for one.
   - Keep it short and to the point — clear enough for a student to understand and memorize, but never an essay.

   5 MARKS:
   - Simple definition or introduction.
   - 4–6 clear points with standard keywords in bold + simple 1-line explanations, or 2–4 clean sub-sections with `### Heading`.
   - Formula, diagram, or simple real-world example where applicable.
   - Moderate depth — cover the topic clearly without unnecessary fluff or heavy jargon.

   10+ MARKS:
   - Simple definition/introduction.
   - Detailed breakdown into clear, logical subsections using standard syllabus terminology with simple explanations.
   - Step-by-step process, formulas, derivations, or ASCII diagrams where applicable.
   - Clear examples and practical applications.
   - Thorough coverage for full marks, keeping language readable and well-structured.

   Never pad an answer with complex filler words, and never write more than the marks justify. Answer length MUST be proportional to the marks. Prioritize standard syllabus terms, simple explanations, technical correctness, clarity, and mark-appropriate depth.

7. NUMERICAL / CALCULATION QUESTIONS (CRITICAL — NEVER ANSWER WITH THEORY ONLY):
   If the question asks to calculate, compute, solve, evaluate, find, determine, or work out a numerical / mathematical problem (e.g., "calculate the max-min composition", "min-max composition", "centroid / defuzzification", "probability", or solving a matrix / numerical problem), you MUST provide a complete WORKED SOLUTION — never just theory or key points.
   - State the formula / method first.
   - Show the calculation step-by-step, including the intermediate steps and values.
   - Clearly show the final answer (e.g., "Therefore, the max-min composition is ...").
   - If the question PROVIDES values / data, use EXACTLY those given values.
   - If the question does NOT provide values, create a small, simple example dataset yourself, clearly state that it is an assumed / example dataset, and solve it completely step-by-step.
   - Keep the explanation simple and exam-friendly. Include the necessary working even when the marks are low — the theory can be short, but the calculation MUST be complete. This requirement takes priority over the brevity rules above for the working itself."""


REVIEWER_SYSTEM_INSTRUCTION = """You are a Senior Academic Reviewer and Grading Professor for University Examination Boards.

Your job is to review a draft exam answer against the study material context and marks allotment, and produce a refined, crystal-clear, student-friendly, high-scoring FINAL answer.

Evaluation Checklist:
1. Simple, Easy-to-Memorize Explanations & Standard Keywords (CRITICAL):
   - Ensure the answer OPENS by explaining the concept in plain, everyday English (short, simple sentences), as if teaching a student for the first time. If the draft opens with a dense, compressed, jargon-packed one-liner, rewrite it into a clear, simple explanation — without adding unnecessary length.
   - Prefer short, clear sentences; break up long, dense ones.
   - Ensure all standard syllabus keywords and technical component names are preserved in **bold** (e.g., "**Scope**", "**Approach**", "**Resources**", etc.). Do NOT alter standard syllabus terms.
   - Ensure each keyword/point is explained with a short, clear sentence in simple words (a simple example is welcome), easy to understand and memorize. Do NOT compress points into dense fragments.
   - Replace any dense, difficult, or overly complex academic jargon with plain, direct English while keeping the exact technical meaning.
   - Ensure technical facts, formulas, and definitions remain 100% accurate.
   - Do NOT add extra content just to lengthen the answer; keep it proportional to the marks.

2. Grounding & Accuracy: Ensure all facts, formulas, and concepts are strictly supported by the study material.

3. Math & Formula Formatting:
   - Ensure inline math uses tight `$formula$` and display math uses `$$\nformula\n$$` with no empty lines inside.
   - Never leave lone `$` symbols on blank lines.
   - Fix any broken brackets like `[ \\mu ... ]` into valid `$$ \\mu ... $$` or `$ \\mu ... $`.
   - Ensure double backslashes `\\\\` in LaTeX environments like `\\begin{cases}`.

4. Structure & Cleanliness:
   - Do NOT restate the question at the top.
   - Remove ALL unsolicited sections not relevant to the question, including:
     Summary, Summary Table, Conclusion, Key Takeaways, Key Notes, Mark Allocation, Grading Rubric, Reviewer Notes.
   - Remove any sentence or paragraph that comments on, describes, justifies, or evaluates the answer itself (e.g., "This answer is concise, uses plain English, and follows the 2-mark requirement..."). The final output must contain ONLY the answer content — never a note about the answer.
   - Do NOT include horizontal rules `---` or `--` anywhere.
   - Do NOT add trailing essay-style concluding sentences after bullet lists.
   - Use `### Heading` subheadings for structure. Do NOT use bold-only headers.
   - Omit any heading or section that is not directly relevant to the question.

5. Mark-Appropriate Depth (enforce length proportional to marks):
   - 2 Marks: A short plain-English explanation (1–2 simple sentences, not an over-compressed one-liner) + at most 2–3 short, clear points with bold keywords. No `###` headings / Example / Formula sections unless the question asked for them. If the draft is bloated or essay-like, TRIM it; if it is an over-compressed jargon one-liner, expand it slightly into a clear, simple explanation.
   - 5 Marks: Simple definition + 4–6 clear points with bold keywords and simple 1-line explanations + formula/example if relevant.
   - 10+ Marks: Detailed explanation in clean subsections, formulas, step-by-step points, examples/diagrams, keeping language simple and scannable.
   - If the question asks to differentiate/compare, ensure the final answer KEEPS a Markdown comparison table. If the question asks for a diagram, ensure the final answer KEEPS the ASCII diagram (fenced code block). Never delete a required table or diagram.

6. Numerical / Calculation Questions: If the question asks to calculate, compute, solve, evaluate, find, determine, or work out a numerical problem, ensure the FINAL answer contains a complete worked solution — the formula / method, the step-by-step calculation with intermediate results, and a clearly stated final answer. If the draft gave only theory or key points, ADD the full worked solution (use the exact values given in the question, or a small clearly-labeled assumed example if none were given). Never reduce a numerical answer to theory only, and never delete a correct worked calculation.

Output: Return ONLY the final, polished student answer in Markdown format. No preamble, no reviewer commentary, no meta-notes."""


FORMAT_SYSTEM_INSTRUCTION = """You are a formatting assistant. You convert a student's existing answer into the application's standard clean Markdown format. This is a FORMATTING task ONLY — never a rewriting task.

PRESERVE CONTENT EXACTLY (CRITICAL):
- Keep the answer's actual wording, meaning, facts, numbers, and examples exactly as written.
- Do NOT invent, add, or remove information. Do NOT paraphrase, expand, shorten, summarize, or "improve" the wording.
- You may only make the minimal edits needed to express the answer's existing structure in Markdown.

FORMATTING RULES (apply only what the content already implies):
- Convert heading-like lines into `### Heading` Markdown headings. If a clear list of points/components has no heading and needs one for structure, you may add a short, neutral heading (e.g. "### Main Components", "### Key Points") — never one that introduces new facts.
- Convert list-like lines into proper Markdown bullets (`- `) or numbered lists (`1.`).
- When a point leads with a term followed by a dash or colon (e.g. "Hardware Architecture – ..."), make that leading term bold: `**Hardware Architecture** – ...`.
- Preserve any existing bold/italic emphasis.
- Format math with LaTeX: inline `$ ... $`, display `$$ ... $$` (no blank lines inside the delimiters). Never use bare `[ ... ]` or `( ... )` for math.
- Put diagrams / ASCII art / code inside fenced code blocks (``` ... ```), left exactly as written.
- Use exactly one blank line between sections. Do NOT add markdown horizontal rules (`---`).
- Do NOT add a Summary, Conclusion, Key Takeaways, or any commentary about the answer.

Output: Return ONLY the normalized Markdown answer — no preamble and no explanation of what you changed."""


def clean_answer_text(text: str) -> str:
    if not text:
        return ""

    # Strip any accidental rubric/scoring feedback leakage from the reviewer
    cleaned = re.sub(
        r"(?:^|\n)(?:Mark Allocation|Grading Rubric|Scoring Breakdown|Reviewer Assessment|Score):[\s\S]*?(?=\n\n|\n[A-Z]|$)",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    # Strip stray markdown horizontal rules
    cleaned = re.sub(r"(?:^|\n)\s*[-*_]{3,}\s*(?=\n|$)", "\n", cleaned)
    cleaned = re.sub(r"(?:^|\n)\s*--\s*(?=\n|$)", "\n", cleaned)

    # Strip a trailing self-referential meta paragraph that describes the answer
    # itself (e.g. "This answer is concise, uses plain English, and follows the
    # 2-mark requirement with a brief introduction plus three bullet points.").
    # Only the FINAL paragraph is considered, and it must BOTH open with a
    # self-referential stem AND contain a meta signal word — so genuine answer
    # content (even a long answer with an early "This solution ..." paragraph) is
    # never removed.
    cleaned = re.sub(
        r"\n\s*\n\s*(?:This answer|This response|This solution|This explanation|The above answer|The answer above|The response above)\b"
        r"(?:(?!\n\s*\n)[\s\S])*?"
        r"(?:concise|plain English|simple English|bullet|mark requirement|marks requirement|jargon|"
        r"explains? them simply|explains? it simply|brief introduction|as requested|as required|"
        r"proportional to the marks?|easy to (?:understand|memori[sz]e))"
        r"(?:(?!\n\s*\n)[\s\S])*\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


_COMPARE_RE = re.compile(r"\b(differentiate|difference|differences|distinguish|compare|comparison|versus|vs\.?)\b", re.IGNORECASE)
_DIAGRAM_RE = re.compile(r"\b(diagram|flow\s*chart|architecture|schematic|draw|sketch)\b", re.IGNORECASE)
_NUMERIC_RE = re.compile(
    r"\b(calculate|calculation|comput(?:e|ation)|solve|evaluate|numerical|determine|find|"
    r"work\s*out|max[\s-]*min|min[\s-]*max|composition|centroid|defuzzif(?:y|ication|ied)?|"
    r"probabilit(?:y|ies)|matrix|matrices|deriv(?:e|ation))\b",
    re.IGNORECASE,
)

# Phrases meaning "use the supplied reference answer EXACTLY" (verbatim), as
# opposed to the softer "use this as reference" (adapt). Verbatim wins only when
# the user explicitly asks for it, so "use this as reference" must NOT match here.
_VERBATIM_RE = re.compile(
    r"(use\s+(this\s+)?(exact|exactly)|exactly\s+this|use\s+this\s+answer|"
    r"generate\s+this\s+(same|exact)|(same|exact)\s+answer|follow\s+this\s+answer\s+exactly|"
    r"verbatim|word[\s-]for[\s-]word|as[\s-]is|as\s+it\s+is|do\s*n'?t\s+change|do\s+not\s+change)",
    re.IGNORECASE,
)


def is_verbatim_reference_instruction(text: str | None) -> bool:
    """True when the user's instruction explicitly asks to use a supplied
    reference answer exactly / verbatim. The softer "use this as reference"
    (adapt while preserving core content) is intentionally excluded."""
    if not text or not text.strip():
        return False
    return bool(_VERBATIM_RE.search(text))


def build_answer_directives(marks: int, question_text: str) -> str:
    """Build explicit, per-question directives so the model reliably respects
    marks-proportional length and produces a comparison table / ASCII diagram
    when the question actually demands one (the system instruction alone is too
    easy to ignore)."""
    q = question_text or ""
    lines: list[str] = []

    lines.append(
        "Write for easy understanding and memorization: explain the concept first in plain, everyday English "
        "(short, simple sentences), then give the key points/components in a clear structured list with simple "
        "explanations and everyday examples. Keep standard technical terms but explain them simply, and do not pad."
    )

    if marks <= 2:
        lines.append(
            f"This is a {marks}-mark question — keep it short but complete: first a 1–2 sentence plain-English "
            "explanation of the concept (not an over-compressed one-liner), then at most 2–3 short, clear points "
            "(a simple sentence each) with bold keywords. Do NOT add ### headings, an Example section, or a Formula "
            "section unless the question explicitly asks. Keep it simple and easy to memorize, never an essay."
        )
    elif marks <= 6:
        lines.append(
            f"This is a {marks}-mark question — give moderate depth: a short definition plus 4–6 clear points "
            "(or 2–4 small sub-sections). Do not pad with filler."
        )
    else:
        lines.append(
            f"This is a {marks}-mark question — give thorough, well-structured depth with clear subsections, "
            "but keep language simple and never pad with filler."
        )

    if _COMPARE_RE.search(q):
        lines.append(
            "This question asks for a comparison/difference — you MUST present the core of the answer as a "
            "Markdown comparison table with a header row (e.g. `| Aspect | A | B |`) covering several distinct aspects."
        )

    if _DIAGRAM_RE.search(q):
        lines.append(
            "This question asks for a diagram — you MUST include a clear ASCII/text diagram inside a fenced code "
            "block (``` ... ```) with clean monospace alignment, alongside a brief explanation."
        )

    if _NUMERIC_RE.search(q):
        lines.append(
            "This is a numerical/calculation question — you MUST show a COMPLETE WORKED SOLUTION, not just theory. "
            "State the formula/method, show the calculation step-by-step with the intermediate results, and clearly "
            "state the final answer. If the question provides values/data, use EXACTLY those given values; if it does "
            "NOT provide values, create a small, simple example dataset, clearly state that it is an assumed example, "
            "and solve it fully step-by-step. Include the full working even if the marks are low (keep the theory "
            "short but the calculation complete)."
        )

    return "\n".join(f"- {ln}" for ln in lines)


def build_rag_prompt(question_text: str, marks: int, context_documents: list[Document], user_instruction: str | None = None, reference_answer: str | None = None) -> tuple[str, list[dict]]:
    sources = []
    context_blocks = []

    for index, doc in enumerate(context_documents, start=1):
        meta = doc.metadata or {}
        res_name = meta.get("resource_name", "Study Material")
        page = meta.get("page", meta.get("page_number", "N/A"))
        chapter = meta.get("chapter", "General")

        source_entry = {
            "resource_id": meta.get("resource_id"),
            "resource_name": res_name,
            "page": page,
            "chapter": chapter,
        }
        if not any(s["resource_name"] == res_name and s["page"] == page for s in sources):
            sources.append(source_entry)

        context_blocks.append(
            f"[Source {index}: {res_name} | Page {page} | Chapter: {chapter}]\n{doc.page_content}"
        )

    context_str = "\n\n".join(context_blocks) if context_blocks else "No specific study material chunks retrieved."

    directives = build_answer_directives(marks, question_text)

    prompt = f"""QUESTION ({marks} Marks):
{question_text}

STUDY MATERIAL CONTEXT:
{context_str}

ANSWER REQUIREMENTS FOR THIS QUESTION:
{directives}

Please generate the complete, mark-appropriate answer for this question using the context above.
Write in simple, clear, easy-to-understand English with accurate technical facts (avoid overly difficult/dense words).
Format all math formulas with $$ and $ delimiters cleanly without stray blank lines inside formulas.
Do NOT include unnecessary summary tables or markdown dividers (---)."""

    if user_instruction and user_instruction.strip():
        prompt += f"""

ADDITIONAL USER INSTRUCTION (high priority — follow this unless it conflicts with factual accuracy or the study material):
{user_instruction.strip()}"""

    if reference_answer and reference_answer.strip():
        prompt += (
            "\n\nREFERENCE ANSWER (HIGH PRIORITY — use this as the PRIMARY BASIS for your answer):\n"
            "Base your answer on the reference answer below. Preserve its core content, its points, its overall "
            "structure, and its example. Adapt only the wording/formatting where needed for clarity and correct "
            "math formatting, and keep everything factually accurate. Do not drop its key points or replace its example.\n"
            "[BEGIN REFERENCE ANSWER]\n"
            f"{reference_answer.strip()}\n"
            "[END REFERENCE ANSWER]"
        )

    return prompt, sources


def review_rag_answer(
    question_text: str,
    marks: int,
    draft_answer: str,
    context_documents: list[Document],
    user_keys: dict[str, str] | None = None,
    user_instruction: str | None = None,
    reference_answer: str | None = None,
) -> str:
    context_str = "\n\n".join(
        [f"- [Page {doc.metadata.get('page', 'N/A')}]: {doc.page_content}" for doc in context_documents]
    )

    directives = build_answer_directives(marks, question_text)

    review_prompt = f"""QUESTION ({marks} Marks):
{question_text}

STUDY MATERIAL CONTEXT:
{context_str}

DRAFT ANSWER:
{draft_answer}

ANSWER REQUIREMENTS FOR THIS QUESTION:
{directives}

Perform your Academic Review. Make sure the explanation is simple, direct, and easy to understand (replace any hard/dense words with clear, simple terms while preserving exact technical meaning). Ensure the final answer respects the ANSWER REQUIREMENTS above (keep the length proportional to the marks; keep any required comparison table or ASCII diagram intact). Ensure math formulas ($$ / $) are formatted cleanly, remove any unsolicited summary tables or markdown horizontal rules (---), and return ONLY the final answer."""

    if user_instruction and user_instruction.strip():
        review_prompt += f"""

ADDITIONAL USER INSTRUCTION (high priority — honor it in the final answer unless it conflicts with factual accuracy):
{user_instruction.strip()}"""

    if reference_answer and reference_answer.strip():
        review_prompt += (
            "\n\nREFERENCE ANSWER (HIGH PRIORITY — the draft was based on this):\n"
            "Keep the final answer faithful to the reference answer below — preserve its core content, points, "
            "structure, and example. Do not summarize it away, drop its points, or replace its example; only refine "
            "wording, clarity, and math formatting.\n"
            "[BEGIN REFERENCE ANSWER]\n"
            f"{reference_answer.strip()}\n"
            "[END REFERENCE ANSWER]"
        )

    try:
        short_q = question_text[:50] + "..." if len(question_text) > 50 else question_text
        reviewed_answer = call_review(
            prompt=review_prompt,
            system_instruction=REVIEWER_SYSTEM_INSTRUCTION,
            user_keys=user_keys,
            task_name=f"AI Reviewer ({marks}M: '{short_q}')",
        )
        cleaned = clean_answer_text(reviewed_answer)
        return cleaned if cleaned and len(cleaned) > 30 else clean_answer_text(draft_answer)
    except Exception:
        return clean_answer_text(draft_answer)


def generate_rag_answer(
    db,
    user_id: int,
    question_text: str,
    marks: int,
    resource_ids: list[int],
    limit: int = 5,
    enable_review: bool = True,
    user_instruction: str | None = None,
    reference_answer: str | None = None,
) -> dict:
    # 1. Verify user has configured all 4 required free keys
    check_user_has_all_required_keys(db=db, user_id=user_id)
    user_keys = get_user_all_keys(db=db, user_id=user_id)

    # 2. Retrieve relevant chunks from Qdrant with resource filter
    retrieved_docs = retrieve_relevant_documents(
        question=question_text,
        resource_ids=resource_ids,
        user_keys=user_keys,
        limit=limit,
    )

    # 3. Build prompt and collected source references
    prompt, sources = build_rag_prompt(
        question_text=question_text,
        marks=marks,
        context_documents=retrieved_docs,
        user_instruction=user_instruction,
        reference_answer=reference_answer,
    )

    # 4. Draft Answer Generation using multi-provider router
    short_q = question_text[:50] + "..." if len(question_text) > 50 else question_text
    draft_answer = call_generation(
        prompt=prompt,
        system_instruction=DRAFT_SYSTEM_INSTRUCTION,
        user_keys=user_keys,
        task_name=f"RAG Solution Generation ({marks}M: '{short_q}')",
    )

    # 5. AI Answer Reviewer Pass
    final_content = clean_answer_text(draft_answer)
    if enable_review and final_content:
        final_content = review_rag_answer(
            question_text=question_text,
            marks=marks,
            draft_answer=final_content,
            context_documents=retrieved_docs,
            user_keys=user_keys,
            user_instruction=user_instruction,
            reference_answer=reference_answer,
        )

    return {
        "content": final_content,
        "sources": sources,
    }


def normalize_reference_to_markdown(db, user_id: int, raw_text: str) -> str:
    """Convert a user-supplied reference answer into the app's standard clean
    Markdown WITHOUT changing its wording, meaning, facts, or examples.

    Used by the "use this answer exactly" path so raw plain text is never stored
    directly in the database — the content/meaning is preserved but the standard
    Markdown structure (headings, bullets, bold, LaTeX, code fences) is applied.
    If the formatting model call is unavailable or fails, falls back to the
    cleaned raw text so the save never fails.
    """
    if not raw_text or not raw_text.strip():
        return ""

    raw_clean = clean_answer_text(raw_text)
    try:
        check_user_has_all_required_keys(db=db, user_id=user_id)
        user_keys = get_user_all_keys(db=db, user_id=user_id)
        formatted = call_generation(
            prompt=(
                "Convert the following answer into the application's standard clean Markdown format. "
                "Preserve its wording, meaning, facts, and examples EXACTLY — only add Markdown structure "
                "(headings, bullets, bold lead-in terms, LaTeX for formulas, fenced code blocks for diagrams).\n\n"
                "[BEGIN ANSWER]\n"
                f"{raw_text.strip()}\n"
                "[END ANSWER]"
            ),
            system_instruction=FORMAT_SYSTEM_INSTRUCTION,
            user_keys=user_keys,
            task_name="Reference Answer Markdown Normalization",
        )
        cleaned = clean_answer_text(formatted)
        # Guard against a refusal / truncated response silently discarding the
        # user's answer: only accept the formatted version if it retained a
        # reasonable amount of the original content (formatting only adds markup).
        if cleaned and len(cleaned) >= max(20, int(len(raw_clean) * 0.6)):
            return cleaned
        return raw_clean
    except Exception:
        return raw_clean