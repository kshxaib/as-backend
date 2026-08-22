from langchain_community.document_loaders import PyMuPDFLoader
import os
import tempfile
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.db.models import Resource
from app.rag.embeddings import EMBEDDING_MODEL
from app.rag.vector_store import create_vector_store
from app.users.service import get_user_openai_key


# Download a resource PDF from Cloudinary.
def download_pdf(url: str, destination: str) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    with open(destination, "wb") as file:
        file.write(response.content)


# Load a PDF using LangChain's PyMuPDF loader.
def load_pdf(pdf_path: str) -> list[Document]:
    loader = PyMuPDFLoader(pdf_path)
    return loader.load()


# Split LangChain Documents into smaller chunks.
def split_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    return splitter.split_documents(documents)


# Add AcademicStack-specific metadata to every chunk.
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
            "embedding_model": EMBEDDING_MODEL,
        })

        enriched_documents.append(
            Document(
                page_content=document.page_content,
                metadata=metadata,
            )
        )

    return enriched_documents


# Index one AcademicStack resource
def index_resource(db: Session, resource: Resource) -> int:
    # Step 1 — Verify OpenAI API key before starting
    openai_api_key = get_user_openai_key(db=db, user_id=resource.user_id)

    # Step 2 — Update status
    resource.status = "indexing"
    db.commit()
    db.refresh(resource)

    temporary_pdf_path = None

    try:
        # Step 3 — Create temporary PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_pdf_path = temporary_file.name

        # Step 4 — Download PDF
        download_pdf(url=resource.cloudinary_url, destination=temporary_pdf_path)

        # Step 5 — Load PDF using LangChain
        documents = load_pdf(pdf_path=temporary_pdf_path)
        if not documents:
            raise ValueError("No text could be extracted from the PDF.")

        # Step 6 — Split documents
        chunks = split_documents(documents=documents)
        if not chunks:
            raise ValueError("PDF produced no searchable chunks.")

        # Step 7 — Add AcademicStack metadata
        chunks = enrich_documents(documents=chunks, resource=resource)

        # Step 8 — Create LangChain Qdrant store
        vector_store = create_vector_store(api_key=openai_api_key)

        # Step 9 — Store documents + embeddings
        vector_store.add_documents(documents=chunks)

        # Step 10 — Mark resource indexed
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
        # Always remove temporary PDF.
        if temporary_pdf_path and os.path.exists(temporary_pdf_path):
            os.remove(temporary_pdf_path)