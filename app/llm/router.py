import os
import time
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Fallback environment keys
ENV_KEYS = {
    "gemini": os.getenv("GEMINI_API_KEY"),
    "groq": os.getenv("GROQ_API_KEY"),
    "cerebras": os.getenv("CEREBRAS_API_KEY"),
    "nvidia": os.getenv("NVIDIA_API_KEY"),
    "openai": os.getenv("OPENAI_API_KEY"),
}

PROVIDER_CONFIGS = {
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "default_models": ["llama3.1-70b", "llama3.1-8b"],
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_models": ["gemini-3.6-flash", "gemini-3.1-pro-preview"],
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_models": ["meta/llama-3.3-70b-instruct"],
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_models": ["gpt-4o-mini", "gpt-3.5-turbo"],
    },
}


def _call_provider_openai_compatible(
    provider_name: str,
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
) -> str:
    """Invokes any provider using OpenAI SDK compatible endpoints."""
    config = PROVIDER_CONFIGS.get(provider_name)
    if not config:
        raise ValueError(f"Unknown provider: {provider_name}")

    client = OpenAI(
        api_key=api_key,
        base_url=config["base_url"],
        timeout=60.0,
    )

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    content = response.choices[0].message.content
    return content.strip() if content else ""


def call_llm_with_fallback(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    provider_priority: list[str] | None = None,
    temperature: float = 0.2,
) -> str:
    """
    Executes an LLM call through an ordered list of providers.
    If a provider fails (e.g. rate limit, quota exceeded, connection error),
    it immediately falls back to the next provider in the chain.
    """
    if not provider_priority:
        provider_priority = ["cerebras", "groq", "gemini", "nvidia", "openai"]

    user_keys = user_keys or {}
    last_error = None

    for provider in provider_priority:
        # 1. Resolve API key (User Key has highest priority, then .env key)
        api_key = user_keys.get(provider) or ENV_KEYS.get(provider)
        if not api_key:
            logger.debug(f"Skipping provider {provider}: No API key configured.")
            continue

        config = PROVIDER_CONFIGS.get(provider)
        if not config:
            continue

        models = config["default_models"]

        for model in models:
            try:
                logger.info(f"Attempting LLM call with provider='{provider}', model='{model}'")
                result = _call_provider_openai_compatible(
                    provider_name=provider,
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                )

                if result:
                    logger.info(f"LLM call succeeded with provider='{provider}', model='{model}'")
                    return result

            except Exception as exc:
                last_error = exc
                err_msg = str(exc)
                logger.warning(
                    f"Provider '{provider}' with model '{model}' failed: {err_msg}. Failing over to next model/provider..."
                )
                # Short pause before trying next
                time.sleep(0.1)

    raise RuntimeError(
        f"All configured AI providers failed. Last error: {last_error}. "
        "Please verify your API keys in your Profile settings."
    )


# Specialized Task Wrappers with calibrated provider priorities

def call_extraction(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
) -> str:
    """Extraction priority: Cerebras (14.4k RPD) -> Groq -> Gemini -> NVIDIA -> OpenAI"""
    return call_llm_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        provider_priority=["cerebras", "groq", "gemini", "nvidia", "openai"],
        temperature=0.1,
    )


def call_generation(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
) -> str:
    """RAG Generation priority: Groq -> Gemini -> Cerebras -> NVIDIA -> OpenAI"""
    return call_llm_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        provider_priority=["groq", "gemini", "cerebras", "nvidia", "openai"],
        temperature=0.2,
    )


def call_review(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
) -> str:
    """Academic Review priority: Cerebras -> NVIDIA -> Gemini -> Groq -> OpenAI"""
    return call_llm_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        provider_priority=["cerebras", "nvidia", "gemini", "groq", "openai"],
        temperature=0.15,
    )