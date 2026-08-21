import json
from google import genai


# Call Gemini using the google-genai SDK.
def call_gemini(api_key: str, prompt: str, system_instruction: str = "") -> str:

    if not api_key:
        raise ValueError("Gemini API key is required.")

    client = genai.Client(api_key=api_key)

    contents = prompt

    config = None

    if system_instruction:
        config = genai.types.GenerateContentConfig(
            system_instruction=system_instruction,
        )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=contents,
        config=config,
    )

    return response.text
 