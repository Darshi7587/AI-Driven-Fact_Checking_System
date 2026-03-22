import google.generativeai as genai
from config import GEMINI_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL
import json
import re
import asyncio
import random
import httpx

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


async def call_ollama(prompt: str) -> str:
    base = OLLAMA_BASE_URL.rstrip("/")
    endpoint = f"{base}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        raise GeminiServiceError(
            "Gemini failed and Ollama fallback is unavailable. Ensure Ollama is running and model is pulled.",
            status_code=502,
        ) from e

    text = (data.get("response") or "").strip()
    if not text:
        raise GeminiServiceError(
            "Gemini failed and Ollama returned an empty response.",
            status_code=502,
        )
    return text

async def call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return await call_ollama(prompt)

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
                return await call_ollama(prompt)

            is_rate_limited = "quota" in lowered or "rate" in lowered or "429" in lowered
            if is_rate_limited:
                if attempt < max_attempts - 1:
                    # Exponential backoff with small jitter for bursty provider throttling.
                    delay = (2 ** attempt) + random.uniform(0.0, 0.4)
                    await asyncio.sleep(delay)
                    continue
                return await call_ollama(prompt)

            if attempt == max_attempts - 1:
                return await call_ollama(prompt)

            delay = (2 ** attempt) + random.uniform(0.0, 0.4)
            await asyncio.sleep(delay)

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
