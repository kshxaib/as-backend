from langchain_community.document_loaders import PyMuPDFLoader
import os
import tempfile
import requests
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.db.models import Resource, User
from app.rag.embeddings import EMBEDDING_MODEL
from app.rag.vector_store import create_vector_store
from app.utils.encryption import decrypt_api_key


# Download a resource PDF from Cloudinary.
def download_pdf(url: str, destination: str) -> None:

    response = requests.get(
        url,
        timeout=120,
    )

    response.raise_for_status()

    with open(destination, "wb") as file:
        file.write(response.content)


def load_pdf(
    pdf_path: str,
) -> list[Document]:
    """
    Load a PDF using LangChain's PyMuPDF loader.

    Returns:
        List of LangChain Document objects.

    Each page becomes a Document containing:
        - page_content
        - source metadata
        - page metadata
    """

    loader = PyMuPDFLoader(
        pdf_path,
    )

    return loader.load()


def split_documents(
    documents: list[Document],
) -> list[Document]:
    """
    Split LangChain Documents into smaller chunks.

    Uses LangChain's RecursiveCharacterTextSplitter.

    Chunk configuration:
        chunk_size = 1000 characters
        overlap   = 200 characters
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )

    return splitter.split_documents(
        documents,
    )


def enrich_documents(
    documents: list[Document],
    resource: Resource,
) -> list[Document]:
    """
    Add AcademicStack-specific metadata to every chunk.

    Qdrant will store this metadata along with the vector.
    """

    enriched_documents = []

    for chunk_index, document in enumerate(
        documents
    ):
        metadata = dict(
            document.metadata
        )

        # AcademicStack ownership metadata.
        metadata.update(
            {
                "resource_id": resource.id,
                "resource_name": resource.name,
                "subject": resource.subject,
                "chapter": resource.chapters,
                "visibility": resource.visibility,
                "chunk_index": chunk_index,

                # Record which embedding model created
                # this vector.
                "embedding_model": EMBEDDING_MODEL,
            }
        )

        enriched_documents.append(
            Document(
                page_content=document.page_content,
                metadata=metadata,
            )
        )

    return enriched_documents


def index_resource(
    db: Session,
    resource: Resource,
) -> int:
    """
    Index one AcademicStack resource.

    Complete pipeline:

        PostgreSQL Resource
                ↓
        Decrypt user's Gemini API key
                ↓
        Download PDF from Cloudinary
                ↓
        LangChain PyMuPDFLoader
                ↓
        LangChain Documents
                ↓
        RecursiveCharacterTextSplitter
                ↓
        AcademicStack metadata
                ↓
        Gemini Embeddings
                ↓
        LangChain QdrantVectorStore
                ↓
        Qdrant

    Returns:
        Number of chunks indexed.
    """

    # -----------------------------------------------------
    # Step 1 — Update status
    # -----------------------------------------------------

    resource.status = "indexing"

    db.commit()
    db.refresh(resource)


    temporary_pdf_path = None


    try:
        # -------------------------------------------------
        # Step 2 — Get the resource owner
        # -------------------------------------------------

        user = (
            db.query(User)
            .filter(User.id == resource.user_id)
            .first()
        )

        if user is None:
            raise ValueError(
                "Resource owner was not found."
            )


        # -------------------------------------------------
        # Step 3 — Decrypt Gemini API key
        # -------------------------------------------------

        gemini_api_key = decrypt_api_key(
            user.gemini_api_key_encrypted
        )


        # -------------------------------------------------
        # Step 4 — Create temporary PDF
        # -------------------------------------------------

        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temporary_file:

            temporary_pdf_path = (
                temporary_file.name
            )


        # -------------------------------------------------
        # Step 5 — Download PDF
        # -------------------------------------------------

        download_pdf(
            url=resource.cloudinary_url,
            destination=temporary_pdf_path,
        )


        # -------------------------------------------------
        # Step 6 — Load PDF using LangChain
        # -------------------------------------------------

        documents = load_pdf(
            pdf_path=temporary_pdf_path,
        )

        if not documents:
            raise ValueError(
                "No text could be extracted from the PDF."
            )


        # -------------------------------------------------
        # Step 7 — Split documents
        # -------------------------------------------------

        chunks = split_documents(
            documents=documents,
        )

        if not chunks:
            raise ValueError(
                "PDF produced no searchable chunks."
            )


        # -------------------------------------------------
        # Step 8 — Add AcademicStack metadata
        # -------------------------------------------------

        chunks = enrich_documents(
            documents=chunks,
            resource=resource,
        )


        # -------------------------------------------------
        # Step 9 — Create LangChain Qdrant store
        # -------------------------------------------------

        vector_store = create_vector_store(
            api_key=gemini_api_key,
        )


        # -------------------------------------------------
        # Step 10 — Store documents + embeddings
        # -------------------------------------------------

        vector_store.add_documents(
            documents=chunks,
        )


        # -------------------------------------------------
        # Step 11 — Mark resource indexed
        # -------------------------------------------------

        resource.status = "indexed"

        db.commit()
        db.refresh(resource)


        return len(chunks)


    except Exception:

        resource.status = "indexing_failed"

        db.commit()

        raise


    finally:

        # -------------------------------------------------
        # Always remove temporary PDF.
        # -------------------------------------------------

        if (
            temporary_pdf_path
            and os.path.exists(
                temporary_pdf_path
            )
        ):
            os.remove(
                temporary_pdf_path
            )