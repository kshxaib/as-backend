import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, VectorParams, Distance

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "academicstack_resources"

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


def get_qdrant_client() -> QdrantClient:
    return client


def check_qdrant_connection() -> bool:
    try:
        client.get_collections()
        return True
    except Exception:
        return False


def ensure_collection(vector_size: int = 768) -> None:
    """Create or resize the AcademicStack Qdrant collection to match active embedding dimension."""
    if client.collection_exists(COLLECTION_NAME):
        collection_info = client.get_collection(COLLECTION_NAME)
        existing_size = collection_info.config.params.vectors.size
        if existing_size == vector_size:
            return
        # If dimension changed (e.g. 1536 -> 768), recreate collection
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


def delete_resource_vectors(resource_id: int) -> None:
    """Delete all Qdrant vectors belonging to one resource."""
    client.delete(
        collection_name=COLLECTION_NAME,
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
