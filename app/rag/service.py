import json
import re
from langchain_core.documents import Document

from app.llm.router import call_generation, call_review
from app.rag.retriever import retrieve_relevant_documents
from app.users.service import get_user_all_keys, check_user_has_all_required_keys


DRAFT_SYSTEM_INSTRUCTION = """You are an academic subject matter expert and exam solver for university students.

Your task is to write high-scoring, crystal-clear, student-friendly, syllabus-grounded exam answers based on the provided study material.

Guidelines:
1. Ground your answer strictly in the provided study material. Do not hallucinate or invent facts.

2. PRESERVE STANDARD SYLLABUS KEYWORDS WITH SIMPLE EXPLANATIONS (CRITICAL):
   - ALWAYS preserve exact, standard syllabus terms, technical keywords, and official component names as bold point titles (e.g., "**Scope**", "**Approach**", "**Resources**", "**Schedule**", "**Deliverables**", "**Acceptance Criteria**"). Do NOT replace or rename standard syllabus terms because university examiners specifically award marks for these keywords.
   - The explanation next to each keyword must be direct, simple, and easy to understand and memorize (1 clear line per point).
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
   Return ONLY the student's final answer. Do NOT repeat the question.

   Use the following structure when applicable — omit any section that is not relevant to the question:

   ### [Topic / Concept Name]
   Give a direct, simple, and accurate definition/introduction (1–2 plain sentences).

   ### Why It Is Needed / Key Points / Components
   - **[Standard Keyword / Component]** – Simple, direct explanation.
   - **[Standard Keyword / Component]** – Simple, direct explanation.

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

6. MARK-BASED ANSWER STRUCTURE:

   2 MARKS (KEEP IT VERY SHORT — over-answering here is the most common mistake):
   - Direct, simple definition in 1–2 plain sentences.
   - At most 2–3 concise bullet points with standard keywords in bold (e.g., "**Keyword** – Simple explanation").
   - One key formula or fact ONLY if the question needs it.
   - Do NOT add `###` headings, an Example section, or a Formula section unless the question explicitly asks for one.
   - Keep it crisp; stop the moment the point is made. Never expand a 2-mark answer into an essay.

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

   Never pad an answer with complex filler words, and never write more than the marks justify. Answer length MUST be proportional to the marks. Prioritize standard syllabus terms, simple explanations, technical correctness, clarity, and mark-appropriate depth."""


REVIEWER_SYSTEM_INSTRUCTION = """You are a Senior Academic Reviewer and Grading Professor for University Examination Boards.

Your job is to review a draft exam answer against the study material context and marks allotment, and produce a refined, crystal-clear, student-friendly, high-scoring FINAL answer.

Evaluation Checklist:
1. Standard Syllabus Keywords & Simplicity (CRITICAL):
   - Ensure all standard syllabus keywords and technical component names are preserved in **bold** (e.g., "**Scope**", "**Approach**", "**Resources**", etc.). Do NOT alter standard syllabus terms.
   - Ensure the explanation for each keyword is simple, direct, and easy for students to understand and memorize (1 clear line per point).
   - Replace any dense, difficult, or overly complex academic jargon with plain, direct English.
   - Ensure technical facts, formulas, and definitions remain 100% accurate.

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
   - Do NOT include horizontal rules `---` or `--` anywhere.
   - Do NOT add trailing essay-style concluding sentences after bullet lists.
   - Use `### Heading` subheadings for structure. Do NOT use bold-only headers.
   - Omit any heading or section that is not directly relevant to the question.

5. Mark-Appropriate Depth (enforce length proportional to marks):
   - 2 Marks: Short simple definition + at most 2–3 crisp bullet points with bold keywords. No `###` headings / Example / Formula sections unless the question asked for them. If the draft is bloated, TRIM it down. Stop when done.
   - 5 Marks: Simple definition + 4–6 clear points with bold keywords and simple 1-line explanations + formula/example if relevant.
   - 10+ Marks: Detailed explanation in clean subsections, formulas, step-by-step points, examples/diagrams, keeping language simple and scannable.
   - If the question asks to differentiate/compare, ensure the final answer KEEPS a Markdown comparison table. If the question asks for a diagram, ensure the final answer KEEPS the ASCII diagram (fenced code block). Never delete a required table or diagram.

Output: Return ONLY the final, polished student answer in Markdown format. No preamble, no reviewer commentary, no meta-notes."""


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

    return cleaned.strip()


_COMPARE_RE = re.compile(r"\b(differentiate|difference|differences|distinguish|compare|comparison|versus|vs\.?)\b", re.IGNORECASE)
_DIAGRAM_RE = re.compile(r"\b(diagram|flow\s*chart|architecture|schematic|draw|sketch)\b", re.IGNORECASE)


def build_answer_directives(marks: int, question_text: str) -> str:
    """Build explicit, per-question directives so the model reliably respects
    marks-proportional length and produces a comparison table / ASCII diagram
    when the question actually demands one (the system instruction alone is too
    easy to ignore)."""
    q = question_text or ""
    lines: list[str] = []

    if marks <= 2:
        lines.append(
            f"This is a {marks}-mark question — keep it VERY short: a 1–2 sentence definition plus at most "
            "2–3 concise bullet points. Do NOT add ### headings, an Example section, or a Formula section "
            "unless the question explicitly asks. Stop as soon as the point is made."
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

    return "\n".join(f"- {ln}" for ln in lines)


def build_rag_prompt(question_text: str, marks: int, context_documents: list[Document], user_instruction: str | None = None) -> tuple[str, list[dict]]:
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

    return prompt, sources


def review_rag_answer(
    question_text: str,
    marks: int,
    draft_answer: str,
    context_documents: list[Document],
    user_keys: dict[str, str] | None = None,
    user_instruction: str | None = None,
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
        )

    return {
        "content": final_content,
        "sources": sources,
    }