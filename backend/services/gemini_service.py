import google.generativeai as genai
from config import GEMINI_API_KEY
import json
import re
import asyncio
import random

genai.configure(api_key=GEMINI_API_KEY)


class GeminiServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code

def get_gemini_model():
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            top_p=0.95,
            top_k=40,
        )
    )

async def call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise GeminiServiceError("GEMINI_API_KEY is missing in backend/.env", status_code=400)

    model = get_gemini_model()
    max_attempts = 4

    for attempt in range(max_attempts):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            msg = str(e)
            lowered = msg.lower()

            if "api key not valid" in lowered or "api_key_invalid" in lowered:
                raise GeminiServiceError(
                    "Invalid Gemini API key. Update GEMINI_API_KEY in backend/.env and restart the backend.",
                    status_code=400,
                ) from e

            is_rate_limited = "quota" in lowered or "rate" in lowered or "429" in lowered
            if is_rate_limited:
                if attempt < max_attempts - 1:
                    # Exponential backoff with small jitter for bursty provider throttling.
                    delay = (2 ** attempt) + random.uniform(0.0, 0.4)
                    await asyncio.sleep(delay)
                    continue
                raise GeminiServiceError(
                    "Gemini API quota/rate limit reached. Please retry later.",
                    status_code=429,
                ) from e

            raise GeminiServiceError("Gemini service request failed.", status_code=502) from e

def extract_json_from_text(text: str) -> dict | list:
    """Extract JSON from Gemini response that may include markdown code blocks."""
    # Remove markdown code blocks
    cleaned = re.sub(r'```(?:json)?\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()
    
    # Find JSON content
    json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
