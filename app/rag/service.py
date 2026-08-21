import json
from langchain_core.documents import Document

from app.llm.service import call_openai
from app.rag.retriever import retrieve_relevant_documents


SYSTEM_INSTRUCTION = """You are an academic subject matter expert and exam solver for university students.

Your task is to write high-scoring, structured, syllabus-grounded exam answers based on the provided study material.

Guidelines:
1. Ground your answer strictly in the provided study material. Do not hallucinate or invent facts.
2. Structure your answer clearly using Markdown:
   - Bold key terms and definitions.
   - Use bullet points and numbered steps where appropriate.
   - Include code blocks, formulas, or ASCII diagrams if applicable to the topic.
3. Adapt the answer depth to the marks allotted:
   - 2 Marks: Direct, accurate definition with 2-3 key bullet points (50-100 words).
   - 5 Marks: Comprehensive explanation with definitions, core mechanisms, structured points, and examples (150-250 words).
   - 10+ Marks: Deep, exhaustive university-level answer covering theory, architectural details, steps, pros/cons, comparisons, and real-world use cases (400-600 words).
4. At the end of the answer, add a 'Sources Used' section referencing the relevant source numbers."""


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

Please generate the complete, mark-appropriate answer for this question using the context above."""

    return prompt, sources


def generate_rag_answer(
    openai_api_key: str,
    question_text: str,
    marks: int,
    resource_ids: list[int],
    limit: int = 5,
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

    # 3. Generate answer with OpenAI LLM
    answer_text = call_openai(
        api_key=openai_api_key,
        prompt=prompt,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    return {
        "content": answer_text.strip(),
        "sources": sources,
    }
