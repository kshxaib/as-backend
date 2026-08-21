from langchain_qdrant import QdrantVectorStore

from app.rag.embeddings import create_embedding_model
from app.vector_store.qdrant import  COLLECTION_NAME, get_qdrant_client



def create_vector_store(api_key: str) -> QdrantVectorStore:
    embeddings = create_embedding_model(
        api_key=api_key
    )

    client = get_qdrant_client()

    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings
    )


