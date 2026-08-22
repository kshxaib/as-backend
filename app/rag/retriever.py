from langchain_core.documents import Document
from app.rag.vector_store import create_vector_store


def retrieve_relevant_documents(
    question: str,
    resource_ids: list[int],
    user_keys: dict[str, str] | None = None,
    limit: int = 5,
) -> list[Document]:
    if not question.strip() or not resource_ids:
        return []

    try:
        vector_store = create_vector_store(user_keys=user_keys)

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

        return retriever.invoke(question)
    except Exception:
        return []