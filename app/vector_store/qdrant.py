import os

from qdrant_client import QdrantClient

from dotenv import load_dotenv

load_dotenv()


# Qdrant client used by the application.
client = QdrantClient(
    host=os.getenv("QDRANT_HOST", "localhost"),
    port=int(os.getenv("QDRANT_PORT", "6333")),
)


def get_qdrant_client() -> QdrantClient:
    """
    Return the application's Qdrant client.

    Other services should use this function instead of
    creating their own QdrantClient instances.
    """

    return client


def check_qdrant_connection() -> bool:
    """
    Check whether the application can communicate with Qdrant.

    Returns:
        True  -> Qdrant is reachable.
        False -> Qdrant is unavailable.
    """

    try:
        client.get_collections()
        return True
    except Exception:
        return False