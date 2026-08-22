import logging
import os
import time
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger("academicstack.router")

# Base URLs and default model candidates per provider
PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_models": [
            "liquid/lfm-2.5-2.6b:free",
        ],
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_models": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
        ],
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_models": ["gemini-3.6-flash", "gemini-3.1-pro-preview"],
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_models": [
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "nvidia/nemotron-4-340b-instruct",
        ],
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_models": ["gpt-4o-mini", "gpt-4o"],
    },
}

# Only OpenAI falls back to env. All other providers MUST be user-supplied keys.
OPENAI_ENV_KEY = os.getenv("OPENAI_API_KEY")


def _call_provider_openai_compatible(
    provider_name: str,
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
) -> str:
    config = PROVIDER_CONFIGS.get(provider_name)
    if not config:
        raise ValueError(f"Unknown provider '{provider_name}'")

    extra_headers = {}
    if provider_name == "openrouter":
        extra_headers = {
            "HTTP-Referer": "https://academicstack.app",
            "X-Title": "AcademicStack",
        }

    client = OpenAI(
        api_key=api_key,
        base_url=config["base_url"],
        timeout=60.0,
        default_headers=extra_headers if extra_headers else None,
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
    task_name: str = "AI Processing",
) -> str:
    """
    Executes an LLM call through an ordered list of providers with real-time console tracing.
    All providers use user-supplied API keys only. OpenAI falls back to env if user key is absent.
    """
    if not provider_priority:
        provider_priority = ["openrouter", "groq", "gemini", "nvidia", "openai"]

    user_keys = user_keys or {}
    last_error = None

    print("\n" + "=" * 65)
    print(f"[AI ROUTER] Task: {task_name.upper()}")
    print(f"[AI ROUTER] Priority Chain: {' -> '.join([p.upper() for p in provider_priority])}")
    print("=" * 65)

    for provider in provider_priority:
        # User key has full priority. For OpenAI only, fall back to env key.
        api_key = user_keys.get(provider)
        if not api_key and provider == "openai":
            api_key = OPENAI_ENV_KEY

        if not api_key:
            logger.debug(f"Skipping provider {provider}: No user API key configured.")
            continue

        config = PROVIDER_CONFIGS.get(provider)
        if not config:
            continue

        models = config["default_models"]

        for model in models:
            try:
                print(f"-> [AI ROUTER] Trying Provider: '{provider.upper()}' | Model: '{model}'...")
                logger.info(f"Attempting LLM call with provider='{provider}', model='{model}' for task='{task_name}'")

                start_time = time.time()
                result = _call_provider_openai_compatible(
                    provider_name=provider,
                    api_key=api_key,
                    model=model,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                )
                elapsed = round(time.time() - start_time, 2)

                if result:
                    print(f"[SUCCESS] Provider: '{provider.upper()}' | Model: '{model}' | Time: {elapsed}s | Task: '{task_name}'\n")
                    logger.info(f"LLM call succeeded with provider='{provider}', model='{model}' in {elapsed}s")
                    return result

            except Exception as exc:
                last_error = exc
                err_msg = str(exc)
                print(f"[FAILOVER] Provider '{provider.upper()}' ({model}) failed -> {err_msg[:100]}... Switching to next!")
                logger.warning(
                    f"Provider '{provider}' with model '{model}' failed: {err_msg}. Failing over to next model/provider..."
                )
                time.sleep(0.1)

    print(f"[FAILED] All providers failed for task: '{task_name}'\n")
    raise RuntimeError(
        f"All configured AI providers failed for task '{task_name}'. Last error: {last_error}. "
        "Please verify your API keys in your Profile settings."
    )


# Specialized Task Wrappers with calibrated provider priorities

def call_extraction(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    task_name: str = "Question Extraction",
) -> str:
    """Extraction priority: OpenRouter (free) -> Groq -> Gemini -> NVIDIA -> OpenAI"""
    return call_llm_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        provider_priority=["openrouter", "groq", "gemini", "nvidia", "openai"],
        temperature=0.1,
        task_name=task_name,
    )


def call_generation(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    task_name: str = "RAG Answer Generation",
) -> str:
    """RAG Generation priority: Groq -> Gemini -> OpenRouter -> NVIDIA -> OpenAI"""
    return call_llm_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        provider_priority=["groq", "gemini", "openrouter", "nvidia", "openai"],
        temperature=0.2,
        task_name=task_name,
    )


def call_review(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    task_name: str = "Academic AI Review",
) -> str:
    """Academic Review priority: OpenRouter -> NVIDIA -> Gemini -> Groq -> OpenAI"""
    return call_llm_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        provider_priority=["openrouter", "nvidia", "gemini", "groq", "openai"],
        temperature=0.15,
        task_name=task_name,
    )