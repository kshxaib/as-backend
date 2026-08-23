from langchain_qdrant import QdrantVectorStore

from app.rag.embeddings import get_embeddings_instance, EMBEDDING_MODEL_GEMINI, EMBEDDING_MODEL_OPENAI
from app.vector_store.qdrant import get_collection_name, get_qdrant_client, ensure_collection



def create_vector_store(
    user_keys: dict[str, str] | None = None,
) -> QdrantVectorStore:

    embeddings, dimension, model_name = get_embeddings_instance(
        user_keys=user_keys
    )

    client = get_qdrant_client()

    if model_name == EMBEDDING_MODEL_GEMINI:
        provider = "gemini"
    elif model_name == EMBEDDING_MODEL_OPENAI:
        provider = "openai"
    else:
        raise ValueError(
            f"Unsupported embedding model: {model_name}"
        )

    collection_name = get_collection_name(provider)

    ensure_collection(
        collection_name=collection_name,
        vector_size=dimension,
    )

    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
