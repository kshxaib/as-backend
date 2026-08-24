import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, VectorParams, Distance

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))


COLLECTION_NAME_GEMINI = "academicstack_resources_gemini"
COLLECTION_NAME_OPENAI = "academicstack_resources_openai"


# Support both Managed Qdrant Cloud (URL + API Key) and Local Self-Hosted Docker (Host + Port)
if QDRANT_URL:
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY or None,
        check_compatibility=False,
    )
else:
    client = QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        check_compatibility=False,
    )


def get_collection_name(provider: str) -> str:
    if provider == "gemini":
        return COLLECTION_NAME_GEMINI

    if provider == "openai":
        return COLLECTION_NAME_OPENAI

    raise ValueError(f"Unsupported embedding provider: {provider}")


def get_qdrant_client() -> QdrantClient:
    return client


def check_qdrant_connection() -> bool:
    try:
        client.get_collections()
        return True
    except Exception:
        return False


def ensure_collection(
    collection_name: str,
    vector_size: int,
) -> None:
    if client.collection_exists(collection_name):
        collection_info = client.get_collection(collection_name)
        existing_size = collection_info.config.params.vectors.size

        if existing_size != vector_size:
            raise ValueError(
                f"Qdrant collection '{collection_name}' has dimension "
                f"{existing_size}, but embedding model requires {vector_size}."
            )

        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


def delete_resource_vectors(resource_id: int) -> None:
    """Delete all Qdrant vectors belonging to one resource."""

    for collection_name in (
        COLLECTION_NAME_GEMINI,
        COLLECTION_NAME_OPENAI,
    ):
        if not client.collection_exists(collection_name):
            continue

        client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="metadata.resource_id",
                        match=MatchValue(
                            value=resource_id,
                        ),
                    )
                ]
            ),
        )


def get_indexed_chunk_indices(collection_name: str, resource_id: int) -> set[int]:
    """Retrieve the set of chunk indices already embedded in Qdrant for a given resource."""
    if not client.collection_exists(collection_name):
        return set()

    try:
        results, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="metadata.resource_id",
                        match=MatchValue(
                            value=resource_id,
                        ),
                    )
                ]
            ),
            limit=5000,
            with_payload=True,
            with_vectors=False,
        )

        indices: set[int] = set()
        for point in results:
            if point.payload and "metadata" in point.payload:
                idx = point.payload["metadata"].get("chunk_index")
                if idx is not None:
                    indices.add(int(idx))
        return indices
    except Exception:
        return set()