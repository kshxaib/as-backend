import os
import tempfile
import time
import math
import re
import requests
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Resource
from app.rag.vector_store import create_vector_store
from app.storage.cloudinary import download_file_bytes
from app.users.service import get_user_all_keys, check_user_has_all_required_keys
from app.vector_store.qdrant import get_indexed_chunk_indices


def download_pdf(public_id: str, direct_url: str, destination: str) -> None:
    content = download_file_bytes(public_id=public_id, direct_url=direct_url)
    with open(destination, "wb") as file:
        file.write(content)


def load_pdf(pdf_path: str) -> list[Document]:
    loader = PyMuPDFLoader(pdf_path)
    return loader.load()


def split_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    return splitter.split_documents(documents)


def enrich_documents(documents: list[Document], resource: Resource) -> list[Document]:
    enriched_documents = []

    for chunk_index, document in enumerate(documents):
        metadata = dict(document.metadata)
        metadata.update({
            "resource_id": resource.id,
            "resource_name": resource.name,
            "subject": resource.subject,
            "chapter": resource.chapters,
            "visibility": resource.visibility,
            "chunk_index": chunk_index,
        })

        enriched_documents.append(
            Document(
                page_content=document.page_content,
                metadata=metadata,
            )
        )

    return enriched_documents


class RateLimiter:
    """
    A lightweight rate limiter to enforce requests-per-minute (RPM) limits across embedding batches.
    """
    def __init__(self, requests_per_minute: int = 60):
        self.interval = 60.0 / max(1, requests_per_minute)
        self.last_request_time = 0.0

    def wait(self) -> None:
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_request_time = time.time()


def _add_documents_with_retry(
    vector_store,
    documents: list[Document],
    batch_size: int = 20,
    max_retries: int = 5,
    rate_limiter: RateLimiter | None = None,
) -> None:
    """
    Embeds and stores documents in batches with robust retry handling for 429 rate limits,
    extracting provider retry/reset delays and using exponential backoff.
    """
    total_docs = len(documents)
    if total_docs == 0:
        return

    limiter = rate_limiter or RateLimiter(requests_per_minute=60)

    for i in range(0, total_docs, batch_size):
        batch = documents[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = math.ceil(total_docs / batch_size)

        for attempt in range(max_retries):
            try:
                # Proactive rate limiting before sending batch to provider
                limiter.wait()

                # Native vector_store batch addition
                vector_store.add_documents(documents=batch, batch_size=len(batch))
                break
            except Exception as exc:
                err_str = str(exc)
                is_quota_err = bool(
                    "RESOURCE_EXHAUSTED" in err_str
                    or "429" in err_str
                    or "rate limit" in err_str.lower()
                    or "quota" in err_str.lower()
                )

                if is_quota_err and attempt < max_retries - 1:
                    # Extract provider retry/reset duration if provided by Google/OpenAI
                    retry_match = re.search(
                        r"(?:retry in|retryDelay[^0-9]*)(\d+(?:\.\d+)?)",
                        err_str,
                        re.IGNORECASE,
                    )
                    if retry_match:
                        wait_seconds = math.ceil(float(retry_match.group(1))) + 2
                    else:
                        # Exponential backoff: 6s, 12s, 24s, 48s...
                        wait_seconds = min(6 * (2 ** attempt), 60)

                    print(
                        f"[RATE-LIMIT RETRY] Provider 429 quota hit on batch {batch_num}/{total_batches}. "
                        f"Waiting {wait_seconds}s before attempt {attempt + 2}/{max_retries}..."
                    )
                    time.sleep(wait_seconds)
                else:
                    raise exc


def index_resource(db: Session, resource: Resource) -> int:
    # 1. Verify user has configured all 4 required free keys
    check_user_has_all_required_keys(db=db, user_id=resource.user_id)
    user_keys = get_user_all_keys(db=db, user_id=resource.user_id)

    # 2. Update status
    resource.status = "indexing"
    db.commit()
    db.refresh(resource)

    temporary_pdf_path = None

    try:
        # 3. Create temporary PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_pdf_path = temporary_file.name

        # 4. Download PDF
        download_pdf(public_id=resource.cloudinary_public_id, direct_url=resource.cloudinary_url, destination=temporary_pdf_path)

        # 5. Load PDF using PyMuPDF
        documents = load_pdf(pdf_path=temporary_pdf_path)
        if not documents:
            raise ValueError("No text could be extracted from the PDF.")

        # 6. Split documents into chunks
        chunks = split_documents(documents=documents)
        if not chunks:
            raise ValueError("PDF produced no searchable chunks.")

        # 7. Add AcademicStack metadata
        chunks = enrich_documents(documents=chunks, resource=resource)

        # 8. Create LangChain Qdrant store with dynamic embeddings (Gemini/OpenAI)
        vector_store = create_vector_store(user_keys=user_keys)

        # 9. Check if any chunks were already indexed (e.g. from previous partial run)
        already_indexed = get_indexed_chunk_indices(
            collection_name=vector_store.collection_name,
            resource_id=resource.id,
        )

        pending_chunks = [
            chunk for chunk in chunks
            if chunk.metadata.get("chunk_index") not in already_indexed
        ]

        # 10. Store pending documents + embeddings in Qdrant with rate-limit retries
        if pending_chunks:
            _add_documents_with_retry(
                vector_store=vector_store,
                documents=pending_chunks,
                batch_size=16,
            )

        # 11. Mark resource indexed
        resource.status = "indexed"
        db.commit()
        db.refresh(resource)

        return len(chunks)

    except HTTPException:
        resource.status = "uploaded"
        db.commit()
        raise

    except Exception:
        resource.status = "indexing_failed"
        db.commit()
        raise

    finally:
        if temporary_pdf_path and os.path.exists(temporary_pdf_path):
            os.remove(temporary_pdf_path)