import json
import re
from langchain_core.documents import Document

from app.llm.router import call_generation, call_review
from app.rag.retriever import retrieve_relevant_documents
from app.users.service import get_user_all_keys, check_user_has_all_required_keys


DRAFT_SYSTEM_INSTRUCTION = """You are an academic subject matter expert and exam solver for university students.

Your task is to write high-scoring, cleanly formatted, syllabus-grounded exam answers based on the provided study material.

Guidelines:
1. Ground your answer strictly in the provided study material. Do not hallucinate or invent facts.

2. MATHEMATICAL & LOGICAL FORMULAS (CRITICAL):
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

3. TYPOGRAPHY & STRUCTURE:
   - Use exactly one blank line between sections, definitions, and topics.
   - Use `### Heading` subheadings for clear visual hierarchy. Do NOT use bold-only headers.
   - If an ASCII diagram or architecture flowchart is helpful, wrap it inside a fenced code block (``` ... ```) with clean monospace alignment.
   - Do NOT use markdown dividers `---` or `--` anywhere in your answer.

4. REQUIRED ANSWER FORMAT:
   Return ONLY the student's final answer. Do NOT repeat the question.

   Use the following structure when applicable — omit any section that is not relevant to the question:

   ### Definition
   Give a concise and accurate definition.

   ### 1. [First major concept]
   Explain the concept clearly.
   - Key point
   - Key point

   ### 2. [Second major concept]
   Explain the concept clearly.

   ### Example
   Provide a relevant example only when it materially improves understanding.

   ### Formula
   Introduce the formula naturally and explain its variables/terms.
   $$
   formula
   $$

   For multi-step problems:
   ### Step 1: [Description]
   Explanation.
   ### Step 2: [Description]
   Explanation.

   For comparison questions, use:
   ### [Concept A] vs [Concept B]
   A comparison table may be used ONLY when the question explicitly asks for comparison, differences, or tabular representation.

   NEVER add these sections unless explicitly requested by the question:
   - Summary / Summary Table
   - Conclusion
   - Key Takeaways / Key Notes
   - Mark Allocation / Grading Rubric
   - Reviewer Notes
   - Question (do not restate the question)

   The answer must read naturally as a university examination answer, not as a generated template.

5. MARK-BASED ANSWER STRUCTURE:

   2 MARKS:
   - Direct definition or explanation.
   - One important formula or fact if applicable.
   - 2–3 concise bullet points.
   - Do NOT over-explain. Stop when done.

   5 MARKS:
   - Definition or brief introduction.
   - 2–4 logically ordered sections with `### Heading`.
   - Formula or equation where applicable.
   - Clear explanation with a relevant example.
   - Moderate depth — cover the concept fully but concisely.

   10+ MARKS:
   - Brief introduction or definition.
   - Detailed conceptual explanation broken into logical subsections.
   - Step-by-step process where applicable.
   - Formulas and derivations where applicable.
   - Example or application.
   - Advantages, disadvantages, or comparison ONLY if directly relevant.
   - Sufficient depth for a university-level examination.

   Never pad an answer to meet a word count. Prioritize correctness, completeness, and mark-appropriate depth."""


REVIEWER_SYSTEM_INSTRUCTION = """You are a Senior Academic Reviewer and Grading Professor for University Examination Boards.

Your job is to review a draft exam answer against the study material context and marks allotment, and produce a refined, high-scoring FINAL answer.

Evaluation Checklist:
1. Grounding & Accuracy: Ensure all facts and formulas are strictly supported by the study material.

2. Math & Formula Formatting:
   - Ensure inline math uses tight `$formula$` and display math uses `$$\nformula\n$$` with no empty lines inside.
   - Never leave lone `$` symbols on blank lines.
   - Fix any broken brackets like `[ \\mu ... ]` into valid `$$ \\mu ... $$` or `$ \\mu ... $`.
   - Ensure double backslashes `\\\\` in LaTeX environments like `\\begin{cases}`.

3. Structure & Cleanliness:
   - Do NOT restate the question at the top.
   - Remove ALL unsolicited sections not relevant to the question, including:
     Summary, Summary Table, Conclusion, Key Takeaways, Key Notes, Mark Allocation, Grading Rubric, Reviewer Notes.
   - Do NOT include horizontal rules `---` or `--` anywhere.
   - Use `### Heading` subheadings for structure. Do NOT use bold-only headers.
   - Omit any heading or section that is not directly relevant to the question.

4. Mark-Appropriate Depth:
   - 2 Marks: Concise definition + formula if applicable + 2–3 tight bullet points. Stop when done.
   - 5 Marks: Definition, 2–4 logically ordered sections, formula, explanation, relevant example.
   - 10+ Marks: Detailed conceptual explanation with subsections, formulas, derivations, step-by-step process, example/application, and any comparison only if relevant.
   - Never pad an answer. Prioritize correctness and completeness over length.

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


def build_rag_prompt(question_text: str, marks: int, context_documents: list[Document]) -> tuple[str, list[dict]]:
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

    prompt = f"""QUESTION ({marks} Marks):
{question_text}

STUDY MATERIAL CONTEXT:
{context_str}

Please generate the complete, mark-appropriate answer for this question using the context above.
Format all math formulas with $$ and $ delimiters cleanly without stray blank lines inside formulas.
Do NOT include unnecessary summary tables unless explicitly requested."""

    return prompt, sources


def review_rag_answer(
    question_text: str,
    marks: int,
    draft_answer: str,
    context_documents: list[Document],
    user_keys: dict[str, str] | None = None,
) -> str:
    context_str = "\n\n".join(
        [f"- [Page {doc.metadata.get('page', 'N/A')}]: {doc.page_content}" for doc in context_documents]
    )

    review_prompt = f"""QUESTION ({marks} Marks):
{question_text}

STUDY MATERIAL CONTEXT:
{context_str}

DRAFT ANSWER:
{draft_answer}

Perform your Academic Review. Ensure math formulas ($$ / $) are formatted cleanly, remove any unsolicited summary tables or markdown horizontal rules (---), and return ONLY the final answer."""

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
        )

    return {
        "content": final_content,
        "sources": sources,
    }