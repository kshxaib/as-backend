import time
from openai import OpenAI


# Call OpenAI with automatic retry on rate limits.
def call_openai(
    api_key: str,
    prompt: str,
    system_instruction: str = "",
    model: str = "gpt-4o-mini",
    max_retries: int = 3,
) -> str:

    if not api_key:
        raise ValueError("OpenAI API key is required.")

    client = OpenAI(api_key=api_key)

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    models_to_try = [model, "gpt-3.5-turbo"]
    last_error = None

    for current_model in models_to_try:
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                )

                content = response.choices[0].message.content
                return content if content else ""

            except Exception as e:
                last_error = e
                err_str = str(e)

                # Rate limited — wait and retry
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait_time = (attempt + 1) * 4
                    time.sleep(wait_time)
                    continue

                # Model not available — try next model
                break

    raise last_error or RuntimeError("OpenAI API call failed after retries.")