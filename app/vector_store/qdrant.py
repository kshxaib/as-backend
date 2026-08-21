import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Filter, VectorParams, Distance


load_dotenv()


QDRANT_HOST = os.getenv("QDRANT_HOST","localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT","6333"))

COLLECTION_NAME = "academicstack_resources"

VECTOR_SIZE = 1536

client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT,
)



def get_qdrant_client() -> QdrantClient:

    return client


def check_qdrant_connection() -> bool:
    try:
        client.get_collections()

        return True

    except Exception:
        return False


# Create the AcademicStack Qdrant collection if it does not already exist.
def ensure_collection() -> None:
    if client.collection_exists(COLLECTION_NAME):
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )


# Delete all Qdrant vectors belonging to one resource.
def delete_resource_vectors(resource_id: int) -> None:

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


