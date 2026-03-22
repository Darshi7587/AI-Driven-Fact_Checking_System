import math
import re
from typing import Dict, List

from services.scraper_service import extract_media_urls, extract_domain, get_trust_score

SUSPICIOUS_MEDIA_TOKENS = {
    "deepfake", "synthetic", "ai-generated", "aigenerated", "midjourney",
    "stable-diffusion", "stablediffusion", "dalle", "runway", "face-swap", "faceswap"
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"}


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _tokenize_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text)


def detect_ai_generated_text(text: str) -> Dict:
    """Estimate probability that text is AI-generated using stylometric heuristics."""
    safe_text = (text or "").strip()
    if not safe_text:
        return {
            "probability": 0.0,
            "label": "unknown",
            "confidence": 0.0,
            "indicators": ["No input text available for analysis"],
            "method": "heuristic-v1",
        }

    words = _tokenize_words(safe_text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", safe_text) if s.strip()]

    total_words = max(len(words), 1)
    total_sentences = max(len(sentences), 1)
    avg_sentence_len = total_words / total_sentences

    unique_ratio = len(set(w.lower() for w in words)) / total_words
    punctuation_density = len(re.findall(r"[,;:()\-]", safe_text)) / max(len(safe_text), 1)

    transition_phrases = [
        "moreover", "furthermore", "in conclusion", "overall", "therefore", "however",
        "additionally", "notably", "in summary", "it is important to note",
    ]
    transition_hits = sum(1 for p in transition_phrases if p in safe_text.lower())

    hedge_terms = ["may", "might", "could", "typically", "generally", "often"]
    hedge_hits = sum(1 for w in words if w.lower() in hedge_terms)

    # Score components tuned for practical signal rather than strict attribution certainty.
    score = 0.0
    indicators = []

    if avg_sentence_len > 24:
        score += 0.9
        indicators.append("Long average sentence length")
    elif avg_sentence_len > 19:
        score += 0.45

    if unique_ratio < 0.42:
        score += 0.8
        indicators.append("Low lexical diversity")
    elif unique_ratio < 0.5:
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

    # Human-like signals decrease score.
    if re.search(r"\b(I|we|my|our)\b", safe_text):
        score -= 0.35
    if re.search(r"\buh|hmm|lol|btw\b", safe_text.lower()):
        score -= 0.45

    probability = round(float(_sigmoid(score - 0.9)), 3)
    label = "likely_ai" if probability >= 0.65 else "likely_human" if probability <= 0.35 else "uncertain"
    confidence = round(abs(probability - 0.5) * 2, 3)

    if not indicators:
        indicators.append("No strong stylometric AI indicators detected")

    return {
        "probability": probability,
        "label": label,
        "confidence": confidence,
        "indicators": indicators[:5],
        "method": "heuristic-v1",
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


async def detect_ai_generated_media(input_type: str, content: str, source_url: str | None = None) -> Dict:
    """Estimate synthetic/deepfake likelihood for media linked in URL input."""
    if input_type != "url":
        return {
            "overall_probability": 0.0,
            "label": "not_applicable",
            "analyzed_count": 0,
            "items": [],
            "note": "Media analysis runs for URL inputs.",
            "method": "heuristic-media-v1",
        }

    page_url = (source_url or content or "").strip()
    if not page_url:
        return {
            "overall_probability": 0.0,
            "label": "unknown",
            "analyzed_count": 0,
            "items": [],
            "note": "No URL available for media analysis.",
            "method": "heuristic-media-v1",
        }

    media_items = await extract_media_urls(page_url, max_items=10)
    if not media_items:
        return {
            "overall_probability": 0.0,
            "label": "no_media_detected",
            "analyzed_count": 0,
            "items": [],
            "note": "No embedded image/audio/video media found on page.",
            "method": "heuristic-media-v1",
        }

    analyzed = []
    probabilities = []

    for item in media_items:
        media_url = item.get("url", "")
        media_type = _infer_media_type(media_url, item.get("type", "unknown"))
        domain = extract_domain(media_url)
        trust = get_trust_score(media_url)

        score = 0.0
        flags = []
        lowered = media_url.lower()

        for token in SUSPICIOUS_MEDIA_TOKENS:
            if token in lowered:
                score += 1.1
                flags.append(f"URL contains suspicious token: {token}")

        if trust < 0.5:
            score += 0.55
            flags.append("Low-trust host domain")
        elif trust >= 0.85:
            score -= 0.45

        if "cdn" in domain or "img" in domain:
            score += 0.15

        probability = round(float(_sigmoid(score - 0.65)), 3)
        probabilities.append(probability)
        analyzed.append({
            "type": media_type,
            "url": media_url,
            "domain": domain,
            "trust_score": round(trust, 3),
            "synthetic_probability": probability,
            "flags": flags[:4],
        })

    overall = round(sum(probabilities) / max(len(probabilities), 1), 3)
    label = "likely_synthetic" if overall >= 0.65 else "likely_authentic" if overall <= 0.35 else "uncertain"

    return {
        "overall_probability": overall,
        "label": label,
        "analyzed_count": len(analyzed),
        "items": analyzed,
        "note": "Heuristic estimate based on media URL patterns and source trust.",
        "method": "heuristic-media-v1",
    }
