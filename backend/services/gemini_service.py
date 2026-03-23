import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_API_KEY_BACKUP, GEMINI_API_KEY_BACKUP_2, GEMINI_API_KEY_BACKUP_3, GEMINI_API_KEY_BACKUP_4, OLLAMA_BASE_URL, OLLAMA_MODEL
import json
import re
import asyncio
import random
import httpx
import time
import threading
from contextvars import ContextVar

MODEL_PREFERENCE: ContextVar[str] = ContextVar("model_preference", default="auto")
MODEL_USED: ContextVar[str] = ContextVar("model_used", default="none")
MODEL_ATTEMPTED: ContextVar[str] = ContextVar("model_attempted", default="none")

# Rate limiter: enforce spacing between API requests to avoid 429 errors
_request_lock = threading.Lock()
_last_request_time = 0.0
_min_request_interval = 0.5  # 0.5 seconds between requests (~120 requests/minute, safe for free tier ~60 req/min)


class GeminiServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def set_model_preference(preference: str):
    pref = (preference or "auto").lower()
    if pref not in {"auto", "gemini", "ollama"}:
        pref = "auto"
    return MODEL_PREFERENCE.set(pref)


def reset_model_preference(token) -> None:
    MODEL_PREFERENCE.reset(token)


def _mark_model_used(model_name: str) -> None:
    current = MODEL_USED.get() or "none"
    if current == "none":
        MODEL_USED.set(model_name)
        return
    if model_name in current.split(","):
        return
    MODEL_USED.set(f"{current},{model_name}")


def _mark_model_attempted(model_name: str) -> None:
    current = MODEL_ATTEMPTED.get() or "none"
    if current == "none":
        MODEL_ATTEMPTED.set(model_name)
        return
    if model_name in current.split(","):
        return
    MODEL_ATTEMPTED.set(f"{current},{model_name}")


def get_model_runtime_info() -> dict:
    attempted = MODEL_ATTEMPTED.get() or "none"
    used = MODEL_USED.get() or "none"

    if used == "none":
        if attempted != "none":
            used = f"{attempted}_failed"
        else:
            used = "rule_based"

    return {
        "selected_model": MODEL_PREFERENCE.get() or "auto",
        "model_used": used,
    }


def clear_model_runtime_info() -> None:
    MODEL_USED.set("none")
    MODEL_ATTEMPTED.set("none")

def _gemini_api_keys() -> list[str]:
    keys = []
    if GEMINI_API_KEY:
        keys.append(GEMINI_API_KEY)
    if GEMINI_API_KEY_BACKUP and GEMINI_API_KEY_BACKUP not in keys:
        keys.append(GEMINI_API_KEY_BACKUP)
    if GEMINI_API_KEY_BACKUP_2 and GEMINI_API_KEY_BACKUP_2 not in keys:
        keys.append(GEMINI_API_KEY_BACKUP_2)
    if GEMINI_API_KEY_BACKUP_3 and GEMINI_API_KEY_BACKUP_3 not in keys:
        keys.append(GEMINI_API_KEY_BACKUP_3)
    if GEMINI_API_KEY_BACKUP_4 and GEMINI_API_KEY_BACKUP_4 not in keys:
        keys.append(GEMINI_API_KEY_BACKUP_4)
    return keys


def get_gemini_model(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            top_p=0.95,
            top_k=40,
        )
    )


def _apply_rate_limit() -> None:
    """Enforce minimum interval between API requests to avoid hitting rate limits."""
    global _last_request_time
    with _request_lock:
        now = time.time()
        time_since_last = now - _last_request_time
        if time_since_last < _min_request_interval:
            sleep_time = _min_request_interval - time_since_last
            time.sleep(sleep_time)
            _last_request_time = time.time()
        else:
            _last_request_time = now


async def call_ollama(prompt: str) -> str:
    _mark_model_attempted("ollama")
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
    _mark_model_used("ollama")
    return text

async def call_gemini(prompt: str) -> str:
    preferred = MODEL_PREFERENCE.get() or "auto"

    if preferred in {"auto", "gemini"}:
        _mark_model_attempted("gemini")

    if preferred == "ollama":
        return await call_ollama(prompt)

    api_keys = _gemini_api_keys()
    if not api_keys:
        raise GeminiServiceError("No Gemini API keys configured.", status_code=502)

    max_attempts_per_key = 3
    last_error = None

    for key_index, api_key in enumerate(api_keys):
        model = get_gemini_model(api_key)

        for attempt in range(max_attempts_per_key):
            try:
                _apply_rate_limit()  # Enforce minimum interval between requests
                response = model.generate_content(prompt)
                _mark_model_used("gemini")
                return response.text
            except Exception as e:
                last_error = e
                msg = str(e)
                lowered = msg.lower()

                invalid_key = "api key not valid" in lowered or "api_key_invalid" in lowered
                is_rate_limited = "quota" in lowered or "rate" in lowered or "429" in lowered

                # Move to next key when current key is invalid or exhausted by quota.
                if invalid_key:
                    break

                if is_rate_limited:
                    if attempt < max_attempts_per_key - 1:
                        delay = (2 ** attempt) + random.uniform(0.0, 0.4)
                        await asyncio.sleep(delay)
                        continue
                    break

                if attempt < max_attempts_per_key - 1:
                    delay = (2 ** attempt) + random.uniform(0.0, 0.4)
                    await asyncio.sleep(delay)
                    continue

                break

        # Small jitter before trying the next key to avoid immediate repeated throttling.
        if key_index < len(api_keys) - 1:
            await asyncio.sleep(0.35)

    err = str(last_error) if last_error else "unknown error"

    # Automatic fallback: if Gemini fails across all keys, try Ollama.
    try:
        return await call_ollama(prompt)
    except Exception as ollama_error:
        raise GeminiServiceError(
            f"Gemini failed on all configured keys ({err}) and Ollama fallback failed: {ollama_error}",
            status_code=502,
        )

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
