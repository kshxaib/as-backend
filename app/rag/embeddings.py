import os
from typing import Tuple
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings

load_dotenv()

EMBEDDING_MODEL_GEMINI = "models/text-embedding-004"
EMBEDDING_DIMENSION_GEMINI = 768

EMBEDDING_MODEL_OPENAI = "text-embedding-3-small"
EMBEDDING_DIMENSION_OPENAI = 1536


def get_embeddings_instance(user_keys: dict[str, str] | None = None) -> Tuple[Embeddings, int, str]:
    """
    Returns an active LangChain Embeddings instance, dimension, and model name.
    Priority:
    1. Gemini API Key (User key or .env) -> 100% Free text-embedding-004 (768-dim)
    2. OpenAI API Key (User key or .env) -> text-embedding-3-small (1536-dim)
    """
    user_keys = user_keys or {}
    gemini_key = user_keys.get("gemini") or os.getenv("GEMINI_API_KEY")
    openai_key = user_keys.get("openai") or os.getenv("OPENAI_API_KEY")

    if gemini_key:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return (
            GoogleGenerativeAIEmbeddings(
                model=EMBEDDING_MODEL_GEMINI,
                google_api_key=gemini_key,
            ),
            EMBEDDING_DIMENSION_GEMINI,
            EMBEDDING_MODEL_GEMINI,
        )
    elif openai_key:
        from langchain_openai import OpenAIEmbeddings
        return (
            OpenAIEmbeddings(
                model=EMBEDDING_MODEL_OPENAI,
                openai_api_key=openai_key,
                dimensions=EMBEDDING_DIMENSION_OPENAI,
            ),
            EMBEDDING_DIMENSION_OPENAI,
            EMBEDDING_MODEL_OPENAI,
        )
    else:
        raise ValueError(
            "No API key found for vector embeddings. Please add your free Google Gemini API key in Profile settings."
        )


def create_embedding_model(user_keys: dict[str, str] | None = None) -> Embeddings:
    embeddings, _, _ = get_embeddings_instance(user_keys=user_keys)
    return embeddings