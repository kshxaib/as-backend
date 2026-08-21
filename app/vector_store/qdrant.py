import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient


load_dotenv()


QDRANT_HOST = os.getenv("QDRANT_HOST","localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT","6333"))

COLLECTION_NAME = "academicstack_resources"

VECTOR_SIZE = 768

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
