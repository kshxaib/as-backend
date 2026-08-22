import json
from langchain_core.documents import Document

from app.llm.service import call_openai
from app.rag.retriever import retrieve_relevant_documents


DRAFT_SYSTEM_INSTRUCTION = """You are an academic subject matter expert and exam solver for university students.

Your task is to write high-scoring, cleanly formatted, syllabus-grounded exam answers based on the provided study material.

Guidelines:
1. Ground your answer strictly in the provided study material. Do not hallucinate or invent facts.

2. MATHEMATICAL & LOGICAL FORMULAS (CRITICAL):
   - Inline math: use single dollar signs without internal newlines, e.g., `$A \cup B$` or `$\mu_A(x)$`.
   - Block equations: put `$$` and the formula on their own line without empty lines inside the delimiter, e.g.:
     $$
     \mu_{A \cup B}(x) = \max(\mu_A(x), \mu_B(x))
     $$
   - Piecewise functions:
     $$
     \mu_{A - B}(x) = \\begin{cases} \mu_A(x) - \mu_B(x) & \\text{if } \mu_A(x) \geq \mu_B(x) \\\\ 0 & \\text{otherwise} \\end{cases}
     $$
   - NEVER output lone dollar signs `$` on blank lines.
   - NEVER use bare square brackets `[ \formula ]` or parentheses `( \formula )` for LaTeX math. ALWAYS use `$$` or `$`.

3. TYPOGRAPHY & SPACING:
   - Use exactly one blank line between sections, definitions, and topics.
   - Do NOT leave excessive empty lines between sentences.
   - Use bold subheadings (e.g., `### 1. Union ($A \cup B$)`) for clear visual hierarchy.

4. Adapt the answer depth to the marks allotted:
   - 2 Marks: Clear definition, formula with `$`/`$$` if applicable, and 2-3 key bullet points (50-100 words).
   - 5 Marks: Comprehensive structured explanation with definitions, equations, step-by-step breakdown, and examples (150-250 words).
   - 10+ Marks: Deep, exhaustive university-level answer covering theory, architectural details, steps, pros/cons, comparisons, and real-world use cases (400-600 words)."""


REVIEWER_SYSTEM_INSTRUCTION = """You are a Senior Academic Reviewer and Grading Professor for University Examination Boards.

Your job is to review a draft exam answer against the study material context and marks allotment, and produce a refined, high-scoring FINAL answer.

Evaluation Checklist:
1. Grounding & Accuracy: Ensure all facts and formulas are strictly supported by the study material.
2. Math & Formula Formatting:
   - Ensure inline math is tight `$A \cup B$` and block math is `$$ formula $$`.
   - Never leave lone `$` symbols on blank lines.
   - Fix any broken brackets like `[ \mu ... ]` into valid `$$ \mu ... $$` or `$ \mu ... $`.
   - Ensure double backslashes `\\\\` in LaTeX environments like `\\begin{cases}`.
3. Clean Spacing:
   - One clean blank line between headings and subquestions. No excessive empty lines.
4. Mark-Appropriate Depth:
   - 2 Marks: Concise, punchy, formulas + key points.
   - 5 Marks: Structured with clear subheadings, formulas, examples.
   - 10+ Marks: Exhaustive academic rigor, step-by-step breakdowns, and comprehensive depth.

Output: Return ONLY the final, polished answer in Markdown format ready for student study."""


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
        # Avoid duplicate source entries
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
Format all math formulas with $$ and $ delimiters cleanly without stray blank lines inside formulas."""

    return prompt, sources


def review_rag_answer(
    openai_api_key: str,
    question_text: str,
    marks: int,
    draft_answer: str,
    context_documents: list[Document],
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

Perform your Academic Review. Ensure math formulas ($$ / $) are formatted cleanly without extra linebreaks and refine the answer for exam scoring."""

    try:
        reviewed_answer = call_openai(
            api_key=openai_api_key,
            prompt=review_prompt,
            system_instruction=REVIEWER_SYSTEM_INSTRUCTION,
        )
        return reviewed_answer.strip() if reviewed_answer and len(reviewed_answer.strip()) > 30 else draft_answer
    except Exception:
        # Fallback gracefully to draft answer if review call hits any issue
        return draft_answer


def generate_rag_answer(
    openai_api_key: str,
    question_text: str,
    marks: int,
    resource_ids: list[int],
    limit: int = 5,
    enable_review: bool = True,
) -> dict:
    # 1. Retrieve relevant chunks from Qdrant with resource filter
    retrieved_docs = retrieve_relevant_documents(
        openai_api_key=openai_api_key,
        question=question_text,
        resource_ids=resource_ids,
        limit=limit,
    )

    # 2. Build prompt and collected source references
    prompt, sources = build_rag_prompt(
        question_text=question_text,
        marks=marks,
        context_documents=retrieved_docs,
    )

    # 3. Step 1: Draft Answer Generation with OpenAI LLM
    draft_answer = call_openai(
        api_key=openai_api_key,
        prompt=prompt,
        system_instruction=DRAFT_SYSTEM_INSTRUCTION,
    )

    # 4. Step 2: AI Answer Reviewer Pass
    final_content = draft_answer.strip()
    if enable_review and final_content:
        final_content = review_rag_answer(
            openai_api_key=openai_api_key,
            question_text=question_text,
            marks=marks,
            draft_answer=final_content,
            context_documents=retrieved_docs,
        )

    return {
        "content": final_content,
        "sources": sources,
    }
