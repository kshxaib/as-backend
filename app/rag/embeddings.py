from typing import Tuple
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

load_dotenv()

EMBEDDING_MODEL_OPENAI = "text-embedding-3-small"
EMBEDDING_DIMENSION_OPENAI = 1536


def get_embeddings_instance(user_keys: dict[str, str] | None = None) -> Tuple[Embeddings, int, str]:
    """
    Returns an active LangChain Embeddings instance powered by OpenAI text-embedding-3-small.
    Key must strictly come from user database record (0 .env fallback).
    """
    user_keys = user_keys or {}
    openai_key = user_keys.get("openai")

    if not openai_key:
        raise ValueError(
            "OpenAI API Key is missing. Please add your OpenAI API key in Profile settings to enable PDF Vector Indexing."
        )

    print(f"\n[VECTOR EMBEDDINGS] Provider: 'OPENAI' | Model: '{EMBEDDING_MODEL_OPENAI}' | Dimensions: {EMBEDDING_DIMENSION_OPENAI}")
    return (
        OpenAIEmbeddings(
            model=EMBEDDING_MODEL_OPENAI,
            api_key=openai_key,
        ),
        EMBEDDING_DIMENSION_OPENAI,
        EMBEDDING_MODEL_OPENAI,
    )


def create_embedding_model(user_keys: dict[str, str] | None = None) -> Embeddings:
    embeddings, _, _ = get_embeddings_instance(user_keys=user_keys)
    return embeddings