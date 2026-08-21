from langchain_core.documents import Document

from app.rag.vector_store import create_vector_store


# Retrieve relevant study material using LangChain.
def retrieve_relevant_documents(gemini_api_key: str, question: str, resource_ids: list[int], limit: int = 5) -> list[Document]:
    if not question.strip():
        return []

    if not resource_ids:
        return []

    vector_store = create_vector_store(
        api_key=gemini_api_key,
    )


    qdrant_filter = {
        "should": [
            {
                "key": "metadata.resource_id",
                "match": {
                    "value": resource_id,
                },
            }
            for resource_id in resource_ids
        ]
    }

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": limit,
            "filter": qdrant_filter,
        },
    )

    return retriever.invoke(
        question,
    )