from langchain_qdrant import QdrantVectorStore

from app.rag.embeddings import get_embeddings_instance
from app.vector_store.qdrant import COLLECTION_NAME, get_qdrant_client, ensure_collection


def create_vector_store(user_keys: dict[str, str] | None = None) -> QdrantVectorStore:
    embeddings, dimension, _ = get_embeddings_instance(user_keys=user_keys)
    client = get_qdrant_client()

    ensure_collection(vector_size=dimension)

    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )
