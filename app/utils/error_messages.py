import math
import re

# Signatures of AI provider quota / rate-limit failures
# (Gemini: "429 RESOURCE_EXHAUSTED ... exceeded your current quota",
#  OpenAI: "Rate limit reached for ...", generic retry hints)
_QUOTA_PATTERN = re.compile(
    r"(RESOURCE_EXHAUSTED|exceeded your current quota|rate limit|\b429\b)",
    re.IGNORECASE,
)

# "limit: 100, model: gemini-embedding-1.0" | "'model': 'gemini-embedding-1.0'"
_MODEL_PATTERN = re.compile(r"model['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9._\-]+)")

# "Please retry in 21.36s" (Google) — preferred, falls back to RPC retryDelay
_RETRY_SECONDS_PATTERN = re.compile(r"(?:[Pp]lease retry in|retry in)\s+([\d.]+)\s*s")
_RETRY_DELAY_FALLBACK_PATTERN = re.compile(r"retryDelay[^0-9]*(\d+(?:\.\d+)?)")

# "limit: 100"
_LIMIT_PATTERN = re.compile(r"limit:\s*(\d+)")


def build_quota_error_detail(raw_error: str) -> str | None:
    """
    Detect AI provider quota / rate-limit failures inside a raw provider error string
    and translate them into one user-friendly message that names the limited model,
    states when the quota resets, and tells the user their options.

    Returns None when the error is not quota-related (caller keeps default handling).
    """
    if not raw_error or not _QUOTA_PATTERN.search(raw_error):
        return None

    model_match = _MODEL_PATTERN.search(raw_error)
    limit_match = _LIMIT_PATTERN.search(raw_error)
    retry_match = _RETRY_SECONDS_PATTERN.search(raw_error) or _RETRY_DELAY_FALLBACK_PATTERN.search(raw_error)

    context_parts = []
    if model_match:
        context_parts.append(f"for model '{model_match.group(1)}'")
    if limit_match:
        context_parts.append(f"(free tier: {limit_match.group(1)} requests/min)")
    context_label = f" {' '.join(context_parts)}" if context_parts else ""

    if retry_match:
        wait_seconds = max(1, math.ceil(float(retry_match.group(1))))
        wait_label = f"in about {wait_seconds} second{'s' if wait_seconds != 1 else ''}"
    else:
        wait_label = "within a minute"

    return (
        "AI rate limit reached while creating vector embeddings"
        f"{context_label}. "
        f"Your quota resets {wait_label}. Please wait for the reset and try again, "
        "or create a different AI provider key for free and update it in settings (Profile Settings)."
    )
