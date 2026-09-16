import logging
import re
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger("academicstack.router")

# Fast, high-capability OpenAI candidate models with automatic failover
OPENAI_EXTRACTION_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
]

OPENAI_GENERATION_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
]

OPENAI_REVIEW_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
]


def _call_openai(
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
) -> str:
    """Executes an LLM call directly against OpenAI API using user's key."""
    client = OpenAI(
        api_key=api_key,
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


def call_openai_with_fallback(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    candidate_models: list[str] | None = None,
    temperature: float = 0.2,
    task_name: str = "AI Processing",
    max_retries_per_model: int = 2,
) -> str:
    """
    Executes an LLM call strictly using OpenAI API with model failover
    (e.g., gpt-4o-mini -> gpt-4o).
    Key must strictly come from user database record (0 .env fallback).
    """
    user_keys = user_keys or {}
    openai_key = user_keys.get("openai")

    if not openai_key:
        raise RuntimeError(
            "OpenAI API Key is missing. "
            "Please add your OpenAI API Key in your Profile settings."
        )

    models = candidate_models or OPENAI_GENERATION_MODELS
    last_error = None

    print("\n" + "=" * 65)
    print(f"[OPENAI ROUTER] Task: {task_name.upper()}")
    print(f"[OPENAI ROUTER] Models Chain: {' -> '.join(models)}")
    print("=" * 65)

    for idx, model in enumerate(models):
        has_fallback_available = idx < len(models) - 1

        for attempt in range(max_retries_per_model):
            try:
                print(f"-> [OPENAI ROUTER] Trying Model: '{model}' (Attempt {attempt + 1})...")
                logger.info(f"Attempting OpenAI call with model='{model}' for task='{task_name}'")

                start_time = time.time()
                result = _call_openai(
                    api_key=openai_key,
                    model=model,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                )
                elapsed = round(time.time() - start_time, 2)

                if result:
                    print(f"[SUCCESS] OpenAI Model: '{model}' | Time: {elapsed}s | Task: '{task_name}'\n")
                    logger.info(f"OpenAI call succeeded with model='{model}' in {elapsed}s")
                    return result

            except Exception as exc:
                last_error = exc
                err_msg = str(exc)
                is_quota = bool(
                    "429" in err_msg
                    or "rate_limit" in err_msg.lower()
                    or "insufficient_quota" in err_msg.lower()
                    or "quota" in err_msg.lower()
                )

                wait_time = 2.0 * (attempt + 1)
                retry_match = re.search(r"(?:retry in|retryDelay[^0-9]*)(\d+(?:\.\d+)?)", err_msg, re.IGNORECASE)
                if retry_match:
                    wait_time = float(retry_match.group(1)) + 1.0

                if wait_time > 10.0 and has_fallback_available:
                    print(f"[FAST FAILOVER] Model '{model}' rate-limited ({wait_time:.0f}s wait). Switching to '{models[idx + 1]}'...")
                    break

                print(f"[FAILOVER] Model '{model}' error -> {err_msg[:90]}... (waiting {wait_time}s)")
                logger.warning(f"Model '{model}' failed: {err_msg}. Retrying / failing over...")
                time.sleep(wait_time)

    print(f"[FAILED] All OpenAI models failed for task: '{task_name}'\n")
    raise RuntimeError(
        f"All OpenAI models failed for task '{task_name}'. Last error: {last_error}. "
        "Please check your OpenAI API key in Profile settings."
    )


# Specialized Task Wrappers powered 100% by OpenAI

def call_extraction(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    task_name: str = "Question Extraction",
) -> str:
    """Extracts questions using OpenAI models."""
    return call_openai_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        candidate_models=OPENAI_EXTRACTION_MODELS,
        temperature=0.1,
        task_name=task_name,
    )


def call_generation(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    task_name: str = "RAG Answer Generation",
) -> str:
    """Generates RAG academic answers using OpenAI models."""
    return call_openai_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        candidate_models=OPENAI_GENERATION_MODELS,
        temperature=0.2,
        task_name=task_name,
    )


def call_review(
    prompt: str,
    system_instruction: str = "",
    user_keys: dict[str, str] | None = None,
    task_name: str = "Academic AI Review",
) -> str:
    """Performs academic grading and rubric review using OpenAI models."""
    return call_openai_with_fallback(
        prompt=prompt,
        system_instruction=system_instruction,
        user_keys=user_keys,
        candidate_models=OPENAI_REVIEW_MODELS,
        temperature=0.15,
        task_name=task_name,
    )