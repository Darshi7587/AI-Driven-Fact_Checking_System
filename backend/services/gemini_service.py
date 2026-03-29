from config import GEMINI_API_KEY, GEMINI_API_KEY_BACKUP, GEMINI_API_KEY_BACKUP_2, GEMINI_API_KEY_BACKUP_3, GEMINI_API_KEY_BACKUP_4, OLLAMA_BASE_URL, OLLAMA_MODEL, HF_API_TOKEN, HF_API_URL
import json
import re
import asyncio
import random
import httpx
import time
import threading
import importlib
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


def _generate_with_gemini_sdk(api_key: str, prompt: str) -> str:
    """Generate text with whichever Gemini SDK is available in the environment."""
    try:
        genai_mod = importlib.import_module("google.genai")
        types_mod = importlib.import_module("google.genai.types")
        client = genai_mod.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types_mod.GenerateContentConfig(
                temperature=0.2,
                top_p=0.95,
                top_k=40,
            ),
        )
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise GeminiServiceError("Gemini returned an empty response.", status_code=502)
        return text
    except ModuleNotFoundError as e:
        raise GeminiServiceError(
            "Gemini SDK not installed in active environment. Install 'google-genai'.",
            status_code=502,
        ) from e


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
        for attempt in range(max_attempts_per_key):
            try:
                _apply_rate_limit()  # Enforce minimum interval between requests
                text = _generate_with_gemini_sdk(api_key=api_key, prompt=prompt)
                _mark_model_used("gemini")
                return text
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


def _clamp_percentage(value, default=50.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = float(default)
    return max(0.0, min(100.0, v))


def _normalize_text_detection_payload(payload: dict) -> dict:
    ai_probability = round(_clamp_percentage(payload.get("ai_probability"), default=50.0), 2)
    confidence = round(_clamp_percentage(payload.get("confidence"), default=50.0), 2)
    label = str(payload.get("label", "Likely Human")).strip()
    if label not in {"Likely AI", "Likely Human"}:
        label = "Likely AI" if ai_probability >= 50.0 else "Likely Human"

    reasoning = payload.get("reasoning", [])
    if not isinstance(reasoning, list):
        reasoning = []
    reasoning = [str(item) for item in reasoning[:3]]
    if not reasoning:
        reasoning = ["Model returned limited explanation."]

    # Include normalized compatibility fields used by existing backend clients.
    probability_0_1 = round(ai_probability / 100.0, 3)
    compat_label = "likely_ai" if ai_probability >= 70 else "likely_human" if ai_probability <= 30 else "uncertain"

    return {
        "ai_probability": ai_probability,
        "label": label,
        "confidence": confidence,
        "reasoning": reasoning,
        "probability": probability_0_1,
        "indicators": reasoning,
        "content_bytes_analyzed": False,
        "confidence_calibration_note": "Confidence reflects the model's certainty under the provided linguistic framework.",
        "method": "gemini-text-detector-v1",
        "compat_label": compat_label,
    }


def _normalize_media_detection_payload(payload: dict) -> dict:
    prediction = str(payload.get("prediction", "Manipulated")).strip()
    if prediction not in {"AI-generated", "Real", "Manipulated", "Possibly AI"}:
        prediction = "Possibly AI"

    confidence = round(_clamp_percentage(payload.get("confidence"), default=45.0), 2)
    ai_probability = round(_clamp_percentage(payload.get("ai_probability"), default=50.0), 2)
    huggingface_score = round(_clamp_percentage(payload.get("huggingface_score", ai_probability), default=ai_probability), 2)

    visual_evidence = payload.get("visual_evidence", payload.get("evidence", payload.get("analysis", [])))
    if not isinstance(visual_evidence, list):
        visual_evidence = []
    visual_evidence = [str(item) for item in visual_evidence[:3]]
    if not visual_evidence:
        visual_evidence = ["Model returned limited visual evidence."]

    final_explanation = str(
        payload.get("final_explanation", payload.get("explanation", "Prediction based on Hugging Face score and visible artifact analysis."))
    ).strip()

    # Existing route/UI compatibility fields.
    overall_probability = round(ai_probability / 100.0, 3)
    label = "likely_synthetic" if ai_probability >= 70 else "likely_authentic" if ai_probability <= 30 else "uncertain"

    return {
        "prediction": prediction,
        "confidence": confidence,
        "ai_probability": ai_probability,
        "huggingface_score": huggingface_score,
        "visual_evidence": visual_evidence,
        "evidence": visual_evidence,
        "final_explanation": final_explanation,
        "analysis": visual_evidence,
        "explanation": final_explanation,
        "overall_probability": overall_probability,
        "label": label,
        "analyzed_count": 1,
        "items": [],
        "content_bytes_analyzed": True,
        "confidence_calibration_note": "Confidence is derived from the model's visual-consistency assessment.",
        "method": "gemini-hf-image-detector-v1",
    }


def _hf_score_only_media_result(hf_score: float, reason: str | None = None) -> dict:
    """Build a deterministic media result from Hugging Face score when Gemini reasoning is unavailable."""
    score = round(_clamp_percentage(hf_score, default=50.0), 2)

    if score > 85:
        prediction = "AI-generated"
        confidence = _clamp_percentage(65 + ((score - 85) * 2), default=80.0)
        evidence = [
            "Hugging Face score is in the strong AI-generated range (>85%).",
            "Primary detector signal was used directly due reasoning-layer unavailability.",
        ]
    elif score >= 60:
        prediction = "AI-generated"
        confidence = _clamp_percentage(55 + ((score - 60) * 1.2), default=70.0)
        evidence = [
            "Hugging Face score indicates likely AI-generated content (60-85%).",
            "Final decision is primarily based on detector probability.",
        ]
    elif score >= 40:
        prediction = "Possibly AI"
        confidence = _clamp_percentage(35 + abs(score - 50) * 1.2, default=42.0)
        evidence = [
            "Hugging Face score is in the uncertain range (40-60%).",
            "Result remains borderline without reasoning-layer corroboration.",
        ]
    else:
        prediction = "Real"
        confidence = _clamp_percentage(55 + ((40 - score) * 1.2), default=70.0)
        evidence = [
            "Hugging Face score is in the likely-real range (<40%).",
            "Primary detector signal suggests authentic camera-captured media.",
        ]

    explanation = (
        f"The Hugging Face detector score is {score}%. "
        "Because the secondary reasoning layer was unavailable, this decision is based on the primary detector threshold policy."
    )

    payload = {
        "prediction": prediction,
        "ai_probability": score,
        "confidence": round(confidence, 2),
        "huggingface_score": score,
        "visual_evidence": evidence,
        "final_explanation": explanation,
        "method": "hf-score-only-v1",
    }
    if reason:
        payload["fallback_reason"] = str(reason)
    return _normalize_media_detection_payload(payload)


def _extract_hf_ai_score_percent(hf_payload) -> float:
    """Extract AI-generated probability from Hugging Face classifier response (0..100)."""
    candidates = hf_payload
    if isinstance(hf_payload, dict):
        for key in ("output", "outputs", "data", "result", "results"):
            if key in hf_payload:
                candidates = hf_payload.get(key)
                break

    if not isinstance(candidates, list) or not candidates:
        raise GeminiServiceError("Hugging Face response did not contain a prediction list.", status_code=502)

    scored = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip().lower()
        score_raw = item.get("score")
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            continue
        scored.append((label, score))

    if not scored:
        raise GeminiServiceError("Hugging Face response labels/scores were not parseable.", status_code=502)

    ai_score = None
    real_score = None
    for label, score in scored:
        if any(tok in label for tok in ("ai", "generated", "synthetic", "deepfake", "fake")):
            ai_score = max(ai_score, score) if ai_score is not None else score
        if any(tok in label for tok in ("real", "human", "authentic", "natural")):
            real_score = max(real_score, score) if real_score is not None else score

    if ai_score is None and real_score is not None:
        ai_score = 1.0 - real_score
    if ai_score is None:
        # Conservative fallback if labels are unknown: use top score as AI probability proxy.
        ai_score = max(score for _, score in scored)

    if ai_score <= 1.0:
        ai_score *= 100.0
    return max(0.0, min(100.0, ai_score))


async def _call_hf_image_detection(file_name: str, content_type: str, file_bytes: bytes) -> float:
    """Call Hugging Face inference API and return AI-generated probability percentage."""
    if not HF_API_TOKEN:
        raise GeminiServiceError("HF_API_TOKEN is not configured.", status_code=502)

    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/octet-stream",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(HF_API_URL, headers=headers, content=file_bytes)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        raise GeminiServiceError(f"Hugging Face API call failed: {e}", status_code=502) from e

    return _extract_hf_ai_score_percent(data)


async def detect_ai_text_with_gemini(text: str) -> dict:
    """Use Gemini to estimate if text is AI-generated and return structured JSON."""
    safe_text = (text or "").strip()
    if len(safe_text) < 10:
        raise GeminiServiceError("Text must be at least 10 characters.", status_code=400)

    prompt = (
        "You are an expert AI content detector trained to distinguish between human-written and AI-generated text.\n\n"
        "Your task is to analyze the given text and determine the probability that it was generated by an AI model.\n\n"
        "Follow this strict evaluation framework:\n"
        "1. Linguistic Patterns:\n"
        "- Check for overly formal, polished, or generic phrasing\n"
        "- Look for lack of personal voice or emotional variability\n"
        "- Detect repetitive sentence structures\n\n"
        "2. Perplexity & Burstiness:\n"
        "- AI text tends to have uniform sentence lengths and predictability\n"
        "- Human text shows irregularity and variation\n\n"
        "3. Specificity:\n"
        "- AI often uses vague, generalized statements\n"
        "- Humans include specific experiences or unique phrasing\n\n"
        "4. Logical Flow:\n"
        "- AI text is often perfectly structured\n"
        "- Humans may include slight inconsistencies\n\n"
        "5. Red Flags:\n"
        "- \"In today's world...\", \"It is important to note...\"\n"
        "- Overuse of connectors and balanced arguments\n\n"
        "Output format (STRICT JSON):\n"
        "{\n"
        "  \"ai_probability\": number (0-100),\n"
        "  \"label\": \"Likely AI\" or \"Likely Human\",\n"
        "  \"confidence\": number (0-100),\n"
        "  \"reasoning\": [\n"
        "    \"point 1\",\n"
        "    \"point 2\",\n"
        "    \"point 3\"\n"
        "  ]\n"
        "}\n\n"
        "Now analyze the following text:\n---\n"
        f"{safe_text}\n"
        "---\n\n"
        "Return JSON only."
    )

    raw = await call_gemini(prompt)
    parsed = extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        raise GeminiServiceError("Gemini returned non-JSON output for text detection.", status_code=502)
    return _normalize_text_detection_payload(parsed)


async def detect_ai_media_with_gemini(file_name: str, content_type: str, file_bytes: bytes) -> dict:
    """Hugging Face-first image detection + Gemini reasoning layer for final decision."""
    if not file_bytes:
        raise GeminiServiceError("Uploaded media file is empty.", status_code=400)

    mime = (content_type or "").lower()
    if not mime.startswith("image/"):
        raise GeminiServiceError("Hugging Face flow is enabled only for image detection.", status_code=400)

    hf_score = await _call_hf_image_detection(
        file_name=file_name,
        content_type=content_type,
        file_bytes=file_bytes,
    )

    try:
        genai_mod = importlib.import_module("google.genai")
        types_mod = importlib.import_module("google.genai.types")
    except ModuleNotFoundError as e:
        # Primary HF detector succeeded; return HF-grounded result if reasoning SDK is unavailable.
        return _hf_score_only_media_result(hf_score=hf_score, reason=f"Gemini SDK unavailable: {e}")

    api_keys = _gemini_api_keys()
    if not api_keys:
        return _hf_score_only_media_result(hf_score=hf_score, reason="No Gemini API keys configured.")

    prompt = (
        "You are an expert AI image authenticity analyst.\n\n"
        "You are given:\n"
        "1. An image\n"
        "2. A probability score from a Hugging Face AI detection model\n\n"
        "Hugging Face Model Result:\n"
        f"AI-generated probability: {round(hf_score, 2)}%\n\n"
        "Your job is to:\n"
        "- Treat the Hugging Face score as the PRIMARY signal\n"
        "- Use visual inspection as SECONDARY support\n"
        "- Produce a final reliable decision\n\n"
        "---\n\n"
        "Decision Guidelines:\n\n"
        "- If score > 85 -> Strong AI-generated signal\n"
        "- If score 60-85 -> Likely AI-generated, verify with artifacts\n"
        "- If score 40-60 -> Uncertain (Possibly AI)\n"
        "- If score < 40 -> Likely real\n\n"
        "---\n\n"
        "Now analyze the image carefully:\n\n"
        "Check for:\n"
        "- Overly smooth or synthetic textures\n"
        "- Inconsistent lighting or shadows\n"
        "- Distorted anatomy (hands, face, symmetry)\n"
        "- Unrealistic background blending\n"
        "- Warped or unreadable text\n\n"
        "---\n\n"
        "Output STRICT JSON:\n\n"
        "{\n"
        "  \"prediction\": \"AI-generated\" or \"Real\" or \"Possibly AI\",\n"
        "  \"ai_probability\": number (0-100),\n"
        "  \"confidence\": number (0-100),\n"
        f"  \"huggingface_score\": {round(hf_score, 2)},\n"
        "  \"visual_evidence\": [\n"
        "    \"specific observation\",\n"
        "    \"specific observation\",\n"
        "    \"specific observation\"\n"
        "  ],\n"
        "  \"final_explanation\": \"Clearly combine the Hugging Face score and visual findings\"\n"
        "}\n\n"
        "---\n\n"
        "Rules:\n"
        "- Do NOT ignore the Hugging Face score\n"
        "- If uncertain -> reduce confidence\n"
        "- Be precise, not generic\n\n"
        f"Filename: {file_name or 'upload'}\n"
        f"MIME type: {content_type or 'application/octet-stream'}\n\n"
        "Return JSON only."
    )

    last_error = None
    max_attempts_per_key = 2
    for key_index, api_key in enumerate(api_keys):
        for attempt in range(max_attempts_per_key):
            try:
                _apply_rate_limit()
                client = genai_mod.Client(api_key=api_key)
                mime = content_type or "application/octet-stream"
                content_part = types_mod.Part.from_bytes(data=file_bytes, mime_type=mime)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt, content_part],
                    config=types_mod.GenerateContentConfig(
                        temperature=0.1,
                        top_p=0.95,
                        top_k=40,
                    ),
                )
                text = (getattr(response, "text", "") or "").strip()
                parsed = extract_json_from_text(text)
                if not isinstance(parsed, dict):
                    raise GeminiServiceError("Gemini returned non-JSON output for media detection.", status_code=502)
                parsed["huggingface_score"] = round(hf_score, 2)
                _mark_model_used("gemini")
                return _normalize_media_detection_payload(parsed)
            except Exception as e:
                last_error = e
                if attempt < max_attempts_per_key - 1:
                    await asyncio.sleep((2 ** attempt) + random.uniform(0.0, 0.4))
                    continue
                break

        if key_index < len(api_keys) - 1:
            await asyncio.sleep(0.35)

    # Keep HF primary signal usable even if Gemini reasoning fails.
    return _hf_score_only_media_result(hf_score=hf_score, reason=f"Gemini media reasoning failed: {last_error}")
