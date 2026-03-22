from services.gemini_service import call_gemini, extract_json_from_text
from services.scraper_service import scrape_url
from typing import List, Dict
import re


def _is_temporal_claim(text: str) -> bool:
    lowered = text.lower()
    temporal_tokens = [
        "currently", "today", "as of", "now", "latest", "recent", "in 20", "by 20", "year",
        "month", "week", "quarter", "century", "decade",
    ]
    return any(token in lowered for token in temporal_tokens)


def _rule_based_claim_fallback(text: str) -> List[Dict]:
    """Fallback extraction when LLM output is malformed or empty."""
    sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
    claims: List[Dict] = []
    seen = set()

    for sentence in sentences:
        for claim_text in _split_compound_claim(sentence):
            claim_text = claim_text.strip().strip('"').strip("'")
            if len(claim_text) < 20:
                continue

            # Keep likely factual statements; filter obvious subjective inputs.
            lowered = claim_text.lower()
            if any(phrase in lowered for phrase in ["i think", "i feel", "in my opinion", "maybe"]):
                continue

            if lowered in seen:
                continue
            seen.add(lowered)

            claims.append({
                "claim_text": claim_text,
                "is_temporal": _is_temporal_claim(claim_text),
                "category": "other",
            })

            if len(claims) >= 10:
                break

        if len(claims) >= 10:
            break

    return claims


def _looks_verifiable(claim_text: str) -> bool:
    lowered = claim_text.lower()
    vague_phrases = [
        "has been growing rapidly",
        "is important",
        "is significant",
        "many people",
        "experts believe",
        "it seems",
        "generally",
        "often",
    ]
    if any(phrase in lowered for phrase in vague_phrases):
        return False

    has_number = bool(re.search(r"\d", claim_text))
    has_date = bool(re.search(r"\b(19|20)\d{2}\b", claim_text))
    has_entity = bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", claim_text))

    # Keep claims with concrete anchors: a number/date or named entities plus factual verbs.
    factual_verbs = ["is", "was", "were", "became", "reported", "announced", "overtook", "ranked", "reached"]
    has_factual_verb = any(f" {v} " in f" {lowered} " for v in factual_verbs)
    return (has_number or has_date or has_entity) and has_factual_verb


def _extract_subject_fragment(text: str) -> str:
    match = re.search(r"^\s*(.+?)\s+\b(is|are|was|were|has|have|had)\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip(" ,.-")


def _split_compound_claim(sentence: str) -> List[str]:
    base = sentence.strip()
    if not base:
        return []

    parts = [p.strip(" ,") for p in re.split(r"\s+(?:and|but)\s+", base) if p.strip(" ,")]
    if len(parts) <= 1:
        return [base]

    subject = _extract_subject_fragment(parts[0])
    claims: List[str] = []

    for idx, part in enumerate(parts):
        normalized = part.strip().rstrip(".")
        if idx > 0 and subject:
            lowered = normalized.lower()
            if lowered.startswith("it "):
                normalized = f"{subject} {normalized[3:]}"
            elif not re.search(r"\b(is|are|was|were|has|have|had|ranked|reached|reported|announced|overtook)\b", lowered):
                # Handle fragments like "strong IT sector" by attaching subject + verb.
                normalized = f"{subject} has {normalized}"

        claims.append(normalized.strip() + ".")

    return claims


def _is_grounded_in_source(claim_text: str, source_text: str) -> bool:
    source_lower = (source_text or "").lower()
    claim_lower = (claim_text or "").lower().strip()
    if not source_lower or not claim_lower:
        return False

    # Strong signal: exact phrase appears in source.
    if claim_lower in source_lower:
        return True

    # Otherwise require high token overlap so the claim cannot drift far from input.
    claim_tokens = [t for t in re.findall(r"[a-z0-9']+", claim_lower) if len(t) > 2]
    if not claim_tokens:
        return False
    overlap = sum(1 for t in claim_tokens if t in source_lower)
    overlap_ratio = overlap / len(claim_tokens)
    return overlap_ratio >= 0.72

async def extract_claims(text: str) -> List[Dict]:
    """
    Extract atomic, verifiable claims from the input text.
    Uses Chain-of-Thought prompting for accuracy.
    """
    prompt = f"""You are an expert fact-checking analyst. Your task is to extract ATOMIC, VERIFIABLE FACTUAL CLAIMS from the following text.

RULES:
1. Extract ONLY objective, factual statements that can be verified with evidence
2. Each claim must be a single, self-contained statement
3. Skip opinions, predictions, and subjective statements
4. Preserve the exact meaning and context
5. Mark if a claim is TEMPORAL (time-sensitive, e.g., "currently", "as of 2024", involves a date/year)
6. Prioritize measurable claims with dates, counts, rankings, named entities, events, and official statements
7. Ignore vague/general descriptions that cannot be directly verified
8. Extract 3-8 most important verifiable claims

INPUT TEXT:
{text[:4000]}

Return ONLY a valid JSON array (no markdown, no extra text):
[
  {{
    "claim_text": "The exact verifiable claim statement",
    "is_temporal": true or false,
    "category": "science|politics|economy|health|sports|technology|history|geography|other"
  }}
]"""

    response = await call_gemini(prompt)
    claims_data = extract_json_from_text(response)

    if isinstance(claims_data, list):
        valid = []
        for claim in claims_data:
            if not isinstance(claim, dict):
                continue
            raw_claim_text = str(claim.get("claim_text", "")).strip()
            for claim_text in _split_compound_claim(raw_claim_text):
                claim_text = claim_text.strip()
                if len(claim_text) < 20:
                    continue
                if not _looks_verifiable(claim_text):
                    continue
                if not _is_grounded_in_source(claim_text, text):
                    continue
                valid.append({
                    "claim_text": claim_text,
                    "is_temporal": bool(claim.get("is_temporal", False)) or _is_temporal_claim(claim_text),
                    "category": str(claim.get("category", "other")),
                })

        if valid:
            deduped = []
            seen = set()
            for c in valid:
                key = c["claim_text"].lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(c)
            return deduped[:10]

    return _rule_based_claim_fallback(text)

async def extract_claims_from_url(url: str) -> tuple[str, List[Dict]]:
    """Scrape URL and extract claims from its content."""
    content = await scrape_url(url)
    if not content:
        raise ValueError(f"Could not scrape content from URL: {url}")
    claims = await extract_claims(content)
    return content, claims
