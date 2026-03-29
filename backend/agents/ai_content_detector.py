import asyncio
import importlib
import math
import re
from collections import Counter
from io import BytesIO
from typing import Dict, List

import httpx

from services.scraper_service import extract_media_urls, extract_domain, get_trust_score


def _get_pillow_image_module():
    try:
        pil_image = importlib.import_module("PIL.Image")
        return pil_image
    except Exception:
        return None

SUSPICIOUS_MEDIA_TOKENS = {
    "deepfake", "synthetic", "ai-generated", "aigenerated", "midjourney",
    "stable-diffusion", "stablediffusion", "dalle", "runway", "face-swap", "faceswap"
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"}
TEXT_URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)

MODELISH_PHRASES = [
    "in conclusion",
    "overall",
    "it is important to note",
    "as an ai",
    "in summary",
    "furthermore",
    "moreover",
    "on the other hand",
    "in today's world",
]

SCHEDULE_PAGE_TOKENS = {
    "schedule", "fixtures", "match", "matches", "venue", "venues", "time table", "upcoming",
    "today match", "full fixtures", "teams", "results", "ipl", "round-robin",
}

TRUSTED_CDN_HINTS = {"toiimg.com", "cdn", "static", "images", "img"}


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _tokenize_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text)


def _char_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(max(p, 1e-12))
    return entropy


def _byte_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(max(p, 1e-12))
    return entropy


def _sentence_split(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _ngram_repetition_ratio(words: List[str], n: int = 3) -> float:
    if len(words) < n:
        return 0.0
    grams = [tuple(w.lower() for w in words[i : i + n]) for i in range(len(words) - n + 1)]
    total = len(grams)
    if total == 0:
        return 0.0
    repeated = sum(1 for c in Counter(grams).values() if c > 1)
    return repeated / total


def _sentence_burstiness(sentences: List[str]) -> float:
    if len(sentences) < 3:
        return 0.0
    lengths = [len(_tokenize_words(s)) for s in sentences]
    mean = sum(lengths) / max(len(lengths), 1)
    if mean == 0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return math.sqrt(variance) / mean


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


def _extract_extension(url: str) -> str:
    cleaned = (url or "").lower().split("?")[0]
    idx = cleaned.rfind(".")
    if idx < 0:
        return ""
    return cleaned[idx:]


def _is_schedule_like_text(text: str) -> bool:
    lowered = (text or "").lower()
    hits = sum(1 for token in SCHEDULE_PAGE_TOKENS if token in lowered)
    return hits >= 3


def detect_ai_generated_text(text: str) -> Dict:
    """Estimate probability that text is AI-generated using advanced stylometric heuristics."""
    safe_text = (text or "").strip()
    if not safe_text:
        return {
            "probability": 0.0,
            "label": "unknown",
            "confidence": 0.0,
            "indicators": ["No input text available for analysis"],
            "content_bytes_analyzed": False,
            "confidence_calibration_note": "Insufficient text content for meaningful confidence calibration.",
            "method": "hybrid-stylometry-v2",
        }

    words = _tokenize_words(safe_text)
    sentences = _sentence_split(safe_text)

    total_words = max(len(words), 1)
    total_sentences = max(len(sentences), 1)
    avg_sentence_len = total_words / total_sentences

    unique_ratio = len(set(w.lower() for w in words)) / total_words
    punctuation_density = len(re.findall(r"[,;:()\-]", safe_text)) / max(len(safe_text), 1)
    burstiness = _sentence_burstiness(sentences)
    char_entropy = _char_entropy(safe_text)
    trigram_repeat = _ngram_repetition_ratio(words, n=3)
    long_sentence_ratio = sum(1 for s in sentences if len(_tokenize_words(s)) >= 30) / total_sentences

    transition_hits = sum(1 for p in MODELISH_PHRASES if p in safe_text.lower())

    hedge_terms = ["may", "might", "could", "typically", "generally", "often"]
    hedge_hits = sum(1 for w in words if w.lower() in hedge_terms)

    is_schedule_like = _is_schedule_like_text(safe_text)

    # Score components tuned for robust demo behavior while preserving uncertainty band.
    score = 0.0
    indicators = []

    if avg_sentence_len > 24:
        score += 0.55 if is_schedule_like else 0.95
        indicators.append("Long average sentence length")
    elif avg_sentence_len > 19:
        score += 0.25 if is_schedule_like else 0.45

    if unique_ratio < 0.42:
        score += 0.85
        indicators.append("Low lexical diversity")
    elif unique_ratio < 0.5:
        score += 0.35

    if trigram_repeat > 0.08:
        score += 0.75
        indicators.append("High phrase repetition pattern")
    elif trigram_repeat > 0.04:
        score += 0.35

    if punctuation_density > 0.04:
        score += 0.5
        indicators.append("High punctuation structure density")

    if transition_hits >= 3:
        score += 0.65
        indicators.append("Frequent structured transition phrases")
    elif transition_hits == 2:
        score += 0.3

    hedge_ratio = hedge_hits / total_words
    if hedge_ratio > 0.035:
        score += 0.45
        indicators.append("Frequent hedging language")

    if long_sentence_ratio > 0.35:
        score += 0.15 if is_schedule_like else 0.35

    if burstiness < 0.25 and total_sentences >= 4:
        score += 0.45
        indicators.append("Low sentence-length burstiness")
    elif burstiness > 0.8:
        score -= 0.25

    if char_entropy < 3.9:
        score += 0.4
    elif char_entropy > 4.8:
        score -= 0.2

    # Human-like signals decrease score.
    if re.search(r"\b(I|we|my|our)\b", safe_text):
        score -= 0.35
        indicators.append("Contains first-person narrative cues")
    if re.search(r"\buh|hmm|lol|btw\b", safe_text.lower()):
        score -= 0.45
        indicators.append("Contains informal conversational markers")

    if re.search(r"\b(don't|can't|won't|i'm|we're|it's|that's)\b", safe_text.lower()):
        score -= 0.2

    if is_schedule_like:
        score -= 0.35
        indicators.append("Schedule/listing-style text pattern detected")

    # Short texts are inherently hard to attribute; damp confidence and score swing.
    if total_words < 45:
        score *= 0.7

    probability = round(float(_sigmoid(score - 1.05)), 3)
    label = "likely_ai" if probability >= 0.70 else "likely_human" if probability <= 0.30 else "uncertain"
    length_factor = _clip(total_words / 220.0, 0.35, 1.0)
    confidence = round(_clip(abs(probability - 0.5) * 2 * length_factor, 0.05, 0.99), 3)

    if not indicators:
        indicators.append("No strong stylometric AI indicators detected")

    confidence_note = (
        "Confidence is calibrated from distance to uncertainty (0.5), then damped for short inputs "
        "to reduce overconfident attribution on limited text."
    )

    return {
        "probability": probability,
        "label": label,
        "confidence": confidence,
        "indicators": indicators[:5],
        "content_bytes_analyzed": False,
        "confidence_calibration_note": confidence_note,
        "method": "hybrid-stylometry-v2",
    }


def _infer_media_type(url: str, fallback_type: str) -> str:
    lowered = url.lower().split("?")[0]
    for ext in IMAGE_EXTENSIONS:
        if lowered.endswith(ext):
            return "image"
    for ext in AUDIO_EXTENSIONS:
        if lowered.endswith(ext):
            return "audio"
    for ext in VIDEO_EXTENSIONS:
        if lowered.endswith(ext):
            return "video"
    return fallback_type


def _extract_media_urls_from_text(text: str, max_items: int = 10) -> List[Dict]:
    seen = set()
    items: List[Dict] = []
    for raw in TEXT_URL_RE.findall(text or ""):
        url = raw.strip().rstrip(",.;)")
        ext = _extract_extension(url)
        media_type = "unknown"
        if ext in IMAGE_EXTENSIONS:
            media_type = "image"
        elif ext in AUDIO_EXTENSIONS:
            media_type = "audio"
        elif ext in VIDEO_EXTENSIONS:
            media_type = "video"
        else:
            continue

        key = f"{media_type}::{url}"
        if key in seen:
            continue
        seen.add(key)
        items.append({"type": media_type, "url": url})
        if len(items) >= max_items:
            break
    return items


async def _fetch_media_sample(client: httpx.AsyncClient, url: str, max_bytes: int = 800_000) -> tuple[bytes, str]:
    # Range request keeps processing fast while still enabling basic forensic signals.
    headers = {"Range": f"bytes=0-{max_bytes - 1}"}
    try:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        return response.content[:max_bytes], content_type
    except Exception:
        return b"", ""


def _analyze_image_bytes(blob: bytes, trust: float) -> tuple[float, List[str]]:
    score = 0.0
    flags: List[str] = []
    if not blob:
        return 0.15, ["Could not fetch image bytes for content analysis"]

    entropy = _byte_entropy(blob)
    if entropy > 7.75:
        score += 0.65
        flags.append("Very high image-byte entropy")
    elif entropy > 7.35:
        score += 0.3

    pil_image = _get_pillow_image_module()
    if pil_image is not None:
        try:
            img = pil_image.open(BytesIO(blob))
            width, height = img.size
            ratio = (max(width, height) / max(min(width, height), 1))
            exif = bool(getattr(img, "getexif", lambda: {})())

            if not exif:
                score += 0.35
                flags.append("Missing EXIF metadata")
            if ratio > 3.4:
                score += 0.2
                flags.append("Unusual aspect ratio")
            if width < 220 or height < 220:
                score += 0.15
            if img.mode in {"RGB", "RGBA"} and trust < 0.55 and not exif:
                score += 0.15
        except Exception:
            score += 0.1
            flags.append("Unable to parse image metadata")

    return score, flags


def _analyze_av_bytes(blob: bytes, media_type: str) -> tuple[float, List[str]]:
    score = 0.0
    flags: List[str] = []
    if not blob:
        return 0.1, ["Could not fetch media bytes for content analysis"]

    entropy = _byte_entropy(blob)
    if entropy > 7.85:
        score += 0.55
        flags.append("Very high media-byte entropy")
    elif entropy < 4.6:
        score += 0.15

    if len(blob) < 80_000:
        score += 0.2
        flags.append(f"Very small {media_type} sample size")

    return score, flags


async def detect_ai_generated_media(input_type: str, content: str, source_url: str | None = None) -> Dict:
    """Estimate synthetic/deepfake likelihood using URL + byte-level media signals."""

    media_items: List[Dict] = []
    if input_type == "url":
        page_url = (source_url or content or "").strip()
        if not page_url:
            return {
                "overall_probability": 0.0,
                "label": "unknown",
                "analyzed_count": 0,
                "items": [],
                "note": "No URL available for media analysis.",
                "content_bytes_analyzed": False,
                "confidence_calibration_note": "No media URLs available, so confidence remains non-informative.",
                "method": "hybrid-media-v2",
            }
        media_items = await extract_media_urls(page_url, max_items=10)
    else:
        media_items = _extract_media_urls_from_text(content or "", max_items=10)

    if not media_items:
        return {
            "overall_probability": 0.0,
            "label": "no_media_detected",
            "analyzed_count": 0,
            "items": [],
            "note": "No analyzable image/audio/video URLs found in input.",
            "content_bytes_analyzed": False,
            "confidence_calibration_note": "No media items detected, so no synthetic-confidence calibration applied.",
            "method": "hybrid-media-v2",
        }

    analyzed = []
    probabilities = []

    async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
        semaphore = asyncio.Semaphore(4)

        async def analyze_item(item: Dict) -> Dict:
            async with semaphore:
                media_url = item.get("url", "")
                media_type = _infer_media_type(media_url, item.get("type", "unknown"))
                domain = extract_domain(media_url)
                trust = get_trust_score(media_url)

                score = 0.0
                flags = []
                lowered = media_url.lower()
                ext = _extract_extension(media_url)

                for token in SUSPICIOUS_MEDIA_TOKENS:
                    if token in lowered:
                        score += 1.0
                        flags.append(f"URL contains suspicious token: {token}")

                if trust < 0.5:
                    score += 0.45
                    flags.append("Low-trust host domain")
                elif trust >= 0.85:
                    score -= 0.35

                # Trusted editorial CDNs should not be penalized like unknown synthetic hosts.
                domain_l = domain.lower()
                if trust >= 0.65 and any(h in domain_l for h in TRUSTED_CDN_HINTS):
                    score -= 0.2
                    flags.append("Trusted news CDN domain")

                blob, content_type = await _fetch_media_sample(client, media_url)
                byte_analysis_used = bool(blob)

                if media_type == "image":
                    content_score, content_flags = _analyze_image_bytes(blob, trust)
                    score += content_score
                    flags.extend(content_flags)
                elif media_type in {"audio", "video"}:
                    content_score, content_flags = _analyze_av_bytes(blob, media_type)
                    score += content_score
                    flags.extend(content_flags)
                else:
                    # Unknown media receives a conservative content-derived estimate.
                    if blob:
                        entropy = _byte_entropy(blob)
                        if entropy > 7.7:
                            score += 0.35
                            flags.append("High byte entropy in unknown media")

                if content_type and media_type == "image" and "image" not in content_type:
                    score += 0.25
                    flags.append("Image URL content-type mismatch")
                if content_type and media_type == "audio" and "audio" not in content_type:
                    score += 0.25
                    flags.append("Audio URL content-type mismatch")
                if content_type and media_type == "video" and "video" not in content_type:
                    score += 0.25
                    flags.append("Video URL content-type mismatch")

                if ext in {".gif", ".svg"}:
                    score += 0.1

                probability = round(float(_sigmoid(score - 1.0)), 3)
                return {
                    "type": media_type,
                    "url": media_url,
                    "domain": domain,
                    "trust_score": round(trust, 3),
                    "synthetic_probability": probability,
                    "content_bytes_analyzed": byte_analysis_used,
                    "confidence_calibration_note": (
                        "Per-item confidence combines URL/domain risk features with media-byte forensic signals "
                        "when bytes are retrievable."
                    ),
                    "flags": flags[:5],
                }

        analyzed = await asyncio.gather(*(analyze_item(item) for item in media_items))

    probabilities = [float(item.get("synthetic_probability", 0.0)) for item in analyzed]

    overall = round(sum(probabilities) / max(len(probabilities), 1), 3)
    label = "likely_synthetic" if overall >= 0.70 else "likely_authentic" if overall <= 0.30 else "uncertain"

    return {
        "overall_probability": overall,
        "label": label,
        "analyzed_count": len(analyzed),
        "items": analyzed,
        "note": "Hybrid estimate from URL risk signals plus media-byte content analysis.",
        "content_bytes_analyzed": any(bool(item.get("content_bytes_analyzed", False)) for item in analyzed),
        "confidence_calibration_note": (
            "Overall confidence is the mean of per-item synthetic probabilities; each item is calibrated from "
            "URL-risk signals and byte-level forensic evidence when available."
        ),
        "method": "hybrid-media-v2",
    }


def detect_ai_generated_uploaded_media(file_name: str, content_type: str, file_bytes: bytes) -> Dict:
    """Estimate synthetic/deepfake likelihood for a single uploaded media file."""
    raw = file_bytes or b""
    file_name_l = (file_name or "upload").lower()
    content_type_l = (content_type or "").lower()

    ext = _extract_extension(file_name_l)
    media_type = "unknown"
    if content_type_l.startswith("image/") or ext in IMAGE_EXTENSIONS:
        media_type = "image"
    elif content_type_l.startswith("audio/") or ext in AUDIO_EXTENSIONS:
        media_type = "audio"
    elif content_type_l.startswith("video/") or ext in VIDEO_EXTENSIONS:
        media_type = "video"

    flags: List[str] = []
    score = 0.0

    if any(token in file_name_l for token in SUSPICIOUS_MEDIA_TOKENS):
        score += 0.65
        flags.append("Filename contains synthetic-media hint tokens")

    if not raw:
        return {
            "overall_probability": 0.0,
            "label": "unknown",
            "prediction": "Manipulated",
            "ai_probability": 0.0,
            "confidence": 0.0,
            "analysis": ["No readable media bytes available for forensic analysis."],
            "explanation": "Unable to classify without media content.",
            "analyzed_count": 0,
            "items": [],
            "note": "Uploaded file has no readable bytes for analysis.",
            "content_bytes_analyzed": False,
            "confidence_calibration_note": "No bytes available, so confidence is non-informative.",
            "method": "hybrid-media-v2",
        }

    if media_type == "image":
        content_score, content_flags = _analyze_image_bytes(raw, trust=0.5)
        score += content_score
        flags.extend(content_flags)

        # Strong combination for synthetic-looking uploads: high entropy + stripped metadata.
        has_high_entropy = any("high image-byte entropy" in f.lower() for f in flags)
        has_missing_exif = any("missing exif" in f.lower() for f in flags)
        if has_high_entropy and has_missing_exif:
            score += 0.15
            flags.append("Entropy/metadata mismatch pattern")

        # Missing EXIF alone is common after social-app compression; keep this weak.
        if content_type_l.startswith("image/") and any("missing exif" in f.lower() for f in flags):
            score += 0.05
    elif media_type in {"audio", "video"}:
        content_score, content_flags = _analyze_av_bytes(raw, media_type)
        score += content_score
        flags.extend(content_flags)
    else:
        entropy = _byte_entropy(raw)
        if entropy > 7.75:
            score += 0.5
            flags.append("High byte entropy in uploaded media")
        elif entropy > 7.35:
            score += 0.25

    if len(raw) < 60_000:
        score += 0.1
        flags.append("Small uploaded sample size")

    # Upload calibration centers image decisions slightly lower than URL-scraped media,
    # because uploads provide direct bytes and fewer crawler/domain priors.
    center = 0.95 if media_type == "image" else 1.0
    probability = round(float(_sigmoid(score - center)), 3)
    label = "likely_synthetic" if probability >= 0.70 else "likely_authentic" if probability <= 0.30 else "uncertain"

    # Blend distance-from-uncertainty with evidence strength so clear forensic cues
    # do not show unrealistically tiny confidence values.
    distance_strength = abs(probability - 0.5) * 2
    evidence_strength = _clip(score / 2.3, 0.05, 0.99)
    confidence_0_1 = _clip((0.75 * distance_strength) + (0.25 * evidence_strength), 0.05, 0.99)

    ai_probability_pct = round(probability * 100.0, 1)
    confidence_pct = round(confidence_0_1 * 100.0, 1)

    if probability >= 0.78:
        prediction = "AI-generated"
    elif probability <= 0.28:
        prediction = "Real"
    else:
        prediction = "Manipulated"

    item = {
        "type": media_type,
        "filename": file_name or "upload",
        "content_type": content_type or "",
        "bytes_analyzed": len(raw),
        "synthetic_probability": probability,
        "content_bytes_analyzed": True,
        "flags": flags[:5] if flags else ["No strong synthetic indicators detected"],
    }

    return {
        "overall_probability": probability,
        "label": label,
        "prediction": prediction,
        "ai_probability": ai_probability_pct,
        "confidence": confidence_pct,
        "analysis": flags[:3] if flags else ["No strong synthetic indicators detected"],
        "explanation": (
            "Classification is based on byte-level forensic signals and available media metadata."
        ),
        "analyzed_count": 1,
        "items": [item],
        "note": "Hybrid estimate from upload metadata and byte-level forensic analysis.",
        "content_bytes_analyzed": True,
        "confidence_calibration_note": (
            "Confidence is derived from media-type-specific byte-level forensic signals and upload metadata risk cues."
        ),
        "method": "hybrid-media-v2",
    }
