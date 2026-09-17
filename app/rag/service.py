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
   - DIAGRAMS: If the question explicitly asks to draw/sketch/show a diagram, flowchart, architecture, or schematic, you MUST include a clean Mermaid.js diagram inside a fenced code block with language `mermaid` (```mermaid ... ```), alongside a brief explanation of each block. Use the correct Mermaid diagram type:
     - `graph TD` or `flowchart TD` for architectures, layer models (OSI/TCP), compiler phases, 3-tier models, and general block diagrams.
     - `sequenceDiagram` for handshakes, client-server interactions, and protocol exchanges.
     - `stateDiagram-v2` for process lifecycles (New → Ready → Running → Terminated), FSMs, and state transitions.
     - `erDiagram` for database entity-relationship diagrams.
   - Mermaid Syntax Rules (CRITICAL for rendering):
     - Keep node IDs short alphanumeric strings (e.g., `A`, `B1`, `CPU`).
     - Enclose labels in square brackets: `A[Application Layer]`.
     - Do NOT use raw parentheses, quotes, or special characters inside node labels — they break rendering.
     - Keep diagrams exam-friendly: 4–8 main blocks, clear directional flow, simple connector labels.
   - If no diagram is explicitly requested, add one ONLY when it genuinely aids understanding (e.g., a 5+ mark architecture question).
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
   - Summary / Summary Table (aside from the required 2-Min Quick Recall block at top)
   - Conclusion
   - Mark Allocation / Grading Rubric
   - Reviewer Notes
   - Question (do not restate the question)
   - Commentary about your own answer — NEVER add a sentence that describes, justifies, or evaluates the answer (e.g., "This answer is concise, uses plain English, and follows the 2-mark requirement with a brief introduction plus three bullet points."). Output ONLY the answer content itself.

6. MARK-BASED ANSWER STRUCTURE & LENGTH SCALING (CRITICAL):

   EVERY answer (regardless of marks) MUST START with a 2-Min Quick Recall snippet block at the very top:
   > **⚡ 2-Min Quick Recall (Exam-Hall TL;DR)**
   > - **[Core Term / Formula]**: Crisp 1-sentence definition or formula.
   > - **[Key Mechanism / Distinction]**: Crisp 1-sentence explanation of working or primary distinction.
   > - **[High-Yield Exam Takeaway]**: 1-sentence critical exam point or pitfall to avoid.

   After the Quick Recall block, scale the core answer strictly to the marks:

   2 MARKS (CRISP & CONCISE — ~60–100 words max, NEVER an essay):
   - 1 plain-English definition sentence (not an over-compressed one-liner).
   - Strictly 2 clear bullet points with bold keywords (e.g., "**Keyword** – 1 simple sentence").
   - Strictly NO diagrams, NO subheadings (###), NO filler or padding.

   5–7 MARKS (MODERATE DEPTH — ~200–300 words):
   - Core explanation (2–3 sentences).
   - 1 concise diagram (flowchart or Mermaid diagram) or structured flow where applicable.
   - 4–6 clear bullet points with bold keywords and 1-line explanations.
   - Clear, focused depth without padding.

   10+ MARKS (COMPREHENSIVE DEPTH — ~450–600 words):
   - In-depth introduction and concept foundation.
   - MANDATORY clean Mermaid diagram (```mermaid ... ```) for architecture, workflow, protocol, or state transition.
   - Detailed breakdown into clear, logical subsections with `### Heading`.
   - Step-by-step mechanisms, formulas, or derivations.
   - Pros & Cons (or Advantages & Limitations / Trade-offs) section.
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

5. Mark-Appropriate Depth & Length Scaling (CRITICAL):
   - Ensure the answer starts with the 2-Min Quick Recall block:
     > **⚡ 2-Min Quick Recall (Exam-Hall TL;DR)**
     > - **[Core Term / Formula]**: Crisp 1-sentence definition.
     > - **[Key Mechanism / Distinction]**: Crisp 1-sentence working or distinction.
     > - **[High-Yield Exam Takeaway]**: 1-sentence critical exam point.
     If the draft omitted this block, construct it from the core points.
   - 2 Marks (~60–100 words max): 1 plain-English definition sentence + strictly 2 clear points with bold keywords. No `###` headings / diagrams / filler. If the draft is bloated or essay-like, aggressively TRIM it to 2 bullet points.
   - 5–7 Marks (~200–300 words): Core explanation (2–3 sentences) + 1 diagram / flowchart + 4–6 clear points with bold keywords.
   - 10+ Marks (~450–600 words): Detailed explanation in clean subsections (`### Heading`), MANDATORY valid Mermaid diagram, step-by-step points/derivations, and a Pros & Cons (or Advantages & Limitations / Trade-offs) section.
   - If the question asks to differentiate/compare, ensure the final answer KEEPS a Markdown comparison table. If the question asks for a diagram, ensure the final answer KEEPS the Mermaid diagram (fenced ```mermaid code block) intact, syntactically valid, and not truncated — never convert it to plain text or ASCII art, and never delete a required diagram.

5b. Mermaid Diagram Validation:
   - If the draft contains a ```mermaid fenced code block, verify it uses valid Mermaid syntax (correct `graph TD`, `sequenceDiagram`, `stateDiagram-v2`, or `erDiagram` header, proper arrow notation `-->`, `==>`, `->>`, and node labels in square brackets `[Label]`).
   - If the Mermaid block is truncated or malformed, FIX it — never delete it. Ensure the diagram has a clear directional flow and exam-appropriate content.

6. Numerical / Calculation Questions: If the question asks to calculate, compute, solve, evaluate, find, determine, or work out a numerical problem, ensure the FINAL answer contains a complete worked solution — the formula / method, the step-by-step calculation with intermediate results, and a clearly stated final answer. If the draft gave only theory or key points, ADD the full worked solution (use the exact values given in the question, or a small clearly-labeled assumed example if none were given). Never reduce a numerical answer to theory only, and never delete a correct worked calculation.

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


def build_answer_directives(marks: int, question_text: str) -> str:
    """Build explicit, per-question directives so the model reliably respects
    marks-proportional length, includes the 2-Min Quick Recall block, and produces
    a comparison table / Mermaid diagram when appropriate."""
    q = question_text or ""
    lines: list[str] = []

    lines.append(
        "Write in SIMPLE TERMS and SIMPLE ENGLISH while keeping the academic meaning strictly intact. "
        "Keep standard technical keywords in bold but explain them in plain, student-friendly sentences. "
        "Answer length MUST be strictly proportional to the marks — never pad with filler words."
    )

    lines.append(
        "MANDATORY EXAM-HALL QUICK RECALL BLOCK: You MUST START your answer with this block at the very top. "
        "List EVERY key term, component, method, or concept from the answer — do NOT limit to 3 points. "
        "Each point must be a bold keyword/term followed by a crisp 1-sentence explanation (max 15 words). "
        "Students standing outside the exam hall should be able to scan ALL key terms in 30 seconds.\n"
        "> **⚡ 2-Min Quick Recall (Exam-Hall TL;DR)**\n"
        "> - **[Term 1]** — crisp 1-sentence explanation (max 15 words).\n"
        "> - **[Term 2]** — crisp 1-sentence explanation (max 15 words).\n"
        "> - **[Term N]** — crisp 1-sentence explanation (max 15 words).\n"
        "Cover ALL terms from the answer, not just 3. Keep each line ultra-short. Followed by the scaled core solution below."
    )

    if marks <= 2:
        lines.append(
            f"This is a {marks}-mark question — CRITICAL BREVITY (~60–100 words max): after the Quick Recall block, "
            "provide 1 plain-English definition sentence, then strictly 2 concise bullet points with bold keywords "
            "(e.g. '**Keyword** – simple 1-sentence explanation'). Do NOT add diagrams, subheadings (###), "
            "Example sections, or Formula sections unless explicitly requested. Over-answering 2-mark questions wastes valuable exam time."
        )
    elif marks <= 7:
        lines.append(
            f"This is a {marks}-mark question — MODERATE DEPTH (~200–300 words): core explanation (2–3 sentences), "
            "1 concise diagram / flow where helpful, and 4–6 clear bullet points with bold keywords and 1-line explanations."
        )
    else:
        lines.append(
            f"This is a {marks}-mark question — COMPREHENSIVE DEPTH (~450–600 words): in-depth concept breakdown, "
            "MANDATORY clean Mermaid diagram (```mermaid ... ```) illustrating architecture/flow/protocol, "
            "detailed logical subsections with ### headings, step-by-step mechanism/derivation, and a "
            "Pros & Cons (or Advantages & Limitations / Trade-offs) section."
        )

    if _COMPARE_RE.search(q):
        lines.append(
            "This question asks for a comparison/difference — you MUST present the core of the answer as a "
            "Markdown comparison table with a header row (e.g. `| Aspect | A | B |`) covering several distinct aspects."
        )

    if _DIAGRAM_RE.search(q):
        lines.append(
            "This question asks for a diagram — you MUST include a clean Mermaid.js diagram inside a fenced code "
            "block with language `mermaid` (```mermaid ... ```). Use `graph TD` or `flowchart TD` for architectures "
            "and block diagrams, `sequenceDiagram` for interactions, `stateDiagram-v2` for state/lifecycle transitions, "
            "or `erDiagram` for ER diagrams. Keep node IDs short (A, B1), use square-bracket labels `[Label]`, "
            "avoid special chars in labels. Add a brief text explanation of each block alongside the diagram."
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