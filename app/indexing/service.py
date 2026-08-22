import os
import tempfile
import requests
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import Resource
from app.rag.vector_store import create_vector_store
from app.users.service import get_user_all_keys


def download_pdf(url: str, destination: str) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    with open(destination, "wb") as file:
        file.write(response.content)


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


def index_resource(db: Session, resource: Resource) -> int:
    # 1. Retrieve all user keys & verify key presence
    user_keys = get_user_all_keys(db=db, user_id=resource.user_id)
    if not user_keys.get("gemini") and not user_keys.get("openai"):
        raise HTTPException(
            status_code=400,
            detail="Gemini API key is required. Please add your free Google Gemini API key in Profile settings to enable vector indexing.",
        )

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
        download_pdf(url=resource.cloudinary_url, destination=temporary_pdf_path)

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

        # 9. Store documents + embeddings in Qdrant
        vector_store.add_documents(documents=chunks)

        # 10. Mark resource indexed
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