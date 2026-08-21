from langchain_google_genai import GoogleGenerativeAIEmbeddings


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768


def create_embedding_model(api_key: str) -> GoogleGenerativeAIEmbeddings:

    if not api_key:
        raise ValueError("Gemini API key is required for embeddings.")

    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
        output_dimensionality=EMBEDDING_DIMENSION,
    )
    