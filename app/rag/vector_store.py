from langchain_qdrant import QdrantVectorStore

from app.rag.embeddings import get_embeddings_instance
from app.vector_store.qdrant import get_collection_name, get_qdrant_client, ensure_collection


def create_vector_store(
    user_keys: dict[str, str] | None = None,
) -> QdrantVectorStore:

    embeddings, dimension, _ = get_embeddings_instance(
        user_keys=user_keys
    )

    client = get_qdrant_client()
    collection_name = get_collection_name("openai")

    ensure_collection(
        collection_name=collection_name,
        vector_size=dimension,
    )

    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
