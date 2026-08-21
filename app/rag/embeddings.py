from langchain_openai import OpenAIEmbeddings


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536


def create_embedding_model(api_key: str) -> OpenAIEmbeddings:

    if not api_key:
        raise ValueError("OpenAI API key is required for embeddings.")

    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=api_key,
        dimensions=EMBEDDING_DIMENSION,
    )