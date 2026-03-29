from services.gemini_service import call_gemini, extract_json_from_text
from services.scraper_service import scrape_url
from typing import List, Dict
import re
from config import FAST_PIPELINE_MODE


def _extract_primary_entity(text: str) -> str:
    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text or "")
    for entity in entities:
        lowered = entity.lower().strip()
        if lowered in {"it", "this", "that", "they", "these", "those"}:
            continue
        return entity.strip()
    return ""


def _resolve_leading_pronoun(claim_text: str, primary_entity: str) -> str:
    if not claim_text or not primary_entity:
        return claim_text
    cleaned = claim_text.strip()
    replaced = re.sub(
        r"^(it|this|that|they|these|those)\b",
        primary_entity,
        cleaned,
        flags=re.IGNORECASE,
    )
    return replaced


def _is_temporal_claim(text: str) -> bool:
    lowered = text.lower()
    temporal_tokens = [
        "currently", "today", "as of", "now", "latest", "recent", "in 20", "by 20", "year",
        "month", "week", "quarter", "century", "decade",
    ]
    return any(token in lowered for token in temporal_tokens)


def _normalize_claim_spacing(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    # Fix common merged-token artifacts from scraped text.
    merged_fixes = {
        r"\bapplehas\b": "apple has",
        r"\blikechatgpt\b": "like chatgpt",
        r"\bapples\b": "apple's",
        r"\bexpectedto\b": "expected to",
        r"\bcompanyannounced\b": "company announced",
        r"\btheapple\b": "the apple",
        r"\bdeveloperyoutube\b": "developer youtube",
        r"\bonthe\b": "on the",
    }
    lowered = cleaned.lower()
    for pattern, replacement in merged_fixes.items():
        lowered = re.sub(pattern, replacement, lowered)
    # Restore sentence capitalization simply.
    return lowered[:1].upper() + lowered[1:] if lowered else lowered

def _is_structurally_sound_claim(text: str) -> bool:
    cleaned = (text or "").strip().strip('"').strip("'")
    if len(cleaned) < 20:
        return False

    lowered = cleaned.lower()
    if re.search(r"\b(when|while|because|although|if|unless)\b", lowered) and "," not in cleaned:
        return False

    # Avoid malformed fragments produced by aggressive clause splitting.
    malformed_patterns = [
        r"\bwhen\b.+\b(is|are|was|were)\b.+\bpreserving\b",
        r"\bhas\s+even\s+centrali[sz]ed\s+control\b",
        r"\bsource\s+article\s*\(input\s+url\)\b",
    ]
    if any(re.search(p, lowered) for p in malformed_patterns):
        return False

    # Require at least one clause verb.
    return bool(re.search(r"\b(is|are|was|were|has|have|had|announced|confirmed|reported|said|stated|led|organized|organised|built|focused|focuses|includes|consists)\b", lowered))


def _is_speculative_claim(text: str) -> bool:
    lowered = (text or "").lower()
    speculative_markers = [
        "expected to", "might", "may ", "likely", "rumored", "rumour", "could",
        "possibly", "potentially", "anticipated", "forecast",
    ]
    factual_anchors = [
        "announced", "confirmed", "press release", "will be held", "scheduled",
        "from ", " on ", " june", " july", " august", " september", " october", " november", " december",
        " january", " february", " march", " april", " may", " event", "conference",
        "signed a deal", "partnership", "introduced", "brought", "integrates", "xcode",
    ]
    has_speculative = any(m in lowered for m in speculative_markers)
    has_factual_anchor = any(a in lowered for a in factual_anchors) or bool(re.search(r"\b(19|20)\d{2}\b", lowered))

    # If speculative language is present alongside a hard factual anchor, keep only when it is primarily factual.
    if has_speculative and has_factual_anchor:
        hard_facts = ["announced", "confirmed", "will be held", "signed a deal", "introduced", "brought"]
        return not any(h in lowered for h in hard_facts)

    return has_speculative and not has_factual_anchor


def _is_low_value_metadata_claim(text: str) -> bool:
    lowered = (text or "").lower().strip()
    metadata_markers = [
        "you can contact", "verify outreach", "based out of", "covers global", "signal",
        "founder summit", "newsletters", "podcasts", "partner content", "contact us",
        "staff events", "strictlyvc", "brand studio", "actively scaling", "fundraising",
        "delve accused", "an exclusive tour", "employees had to", "nothing ceo",
    ]
    if any(m in lowered for m in metadata_markers):
        return True

    # Filter person-bio snippets that are not product/event facts.
    if re.match(r"^(he|she|they)\s+", lowered):
        factual_tokens = ["announced", "launched", "released", "conference", "event", "wwdc", "apple", "google", "xcode", "siri"]
        if not any(t in lowered for t in factual_tokens):
            return True

    return False


def _claim_priority(text: str) -> int:
    lowered = (text or "").lower()
    has_date = bool(re.search(r"\b(19|20)\d{2}\b", lowered)) or bool(
        re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", lowered)
    )
    if "announced" in lowered or "confirmed" in lowered:
        return 3
    if has_date or "will be held" in lowered or "scheduled" in lowered:
        return 2
    return 1


def _rule_based_claim_fallback(text: str) -> List[Dict]:
    """Fallback extraction when LLM output is malformed or empty."""
    sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
    claims: List[Dict] = []
    seen = set()
    primary_entity = _extract_primary_entity(text)

    for sentence in sentences:
        for claim_text in _split_compound_claim(sentence):
            claim_text = _normalize_claim_spacing(claim_text.strip().strip('"').strip("'"))
            claim_text = _resolve_leading_pronoun(claim_text, primary_entity)
            if len(claim_text) < 20:
                continue

            if _is_speculative_claim(claim_text):
                continue
            if _is_low_value_metadata_claim(claim_text):
                continue

            # Filter subjective statements
            lowered = claim_text.lower()
            if any(phrase in lowered for phrase in ["i think", "i feel", "in my opinion", "maybe"]):
                continue
            
            # Apply same verifiability check as LLM path
            if not _looks_verifiable(claim_text):
                continue
            
            # Ground in source text
            if not _is_grounded_in_source(claim_text, text):
                continue

            if lowered in seen:
                continue
            seen.add(lowered)

            claims.append({
                "claim_text": claim_text,
                "is_temporal": _is_temporal_claim(claim_text),
                "category": "other",
                "priority": _claim_priority(claim_text),
            })

            if len(claims) >= 10:
                break

        if len(claims) >= 10:
            break

    if claims:
        claims.sort(key=lambda c: c.get("priority", 1), reverse=True)
        for c in claims:
            c.pop("priority", None)
        return claims

    # Last-resort synthesis for dashboard/data pages where scraped text is metadata-like.
    compact = re.sub(r"\s+", " ", (text or "").strip())
    if not compact:
        return []

    compact = re.sub(r"URL path:.*$", "", compact, flags=re.IGNORECASE).strip()
    compact = re.sub(r"URL:.*$", "", compact, flags=re.IGNORECASE).strip()
    compact = compact.strip(" .|-")

    # For data dashboards, extract key metrics/entities and generate specific claims
    # e.g., "GDP (current US$)" + "India" → "India's GDP data is available"
    metric_pattern = r"\b(GDP|growth|inflation|unemployment|population|income|healthcare|education|poverty)\b"
    metrics = re.findall(metric_pattern, compact, re.IGNORECASE)
    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", compact)
    
    # Remove pronouns from entities
    entities = [e for e in entities if e.lower() not in {"it", "this", "that", "they", "the", "a", "data", "selected", "countries", "economies", "world", "all"}]
    unique_metrics = list(dict.fromkeys(metrics))[:2]  # First 2 unique metrics max
    unique_entities = list(dict.fromkeys(entities))[:2]  # First 2 unique entities max

    generated_claims = []
    
    # Generate claim if we have both entity and metric
    if unique_entities and unique_metrics:
        entity = unique_entities[0]
        metric = unique_metrics[0]
        # Look for context like "current US$" to make claim more specific
        if "current" in compact.lower() and "us$" in compact.lower():
            claim = f"{entity}'s {metric} (current US $) data is reported."
        else:
            claim = f"{entity} has {metric} data available."
        generated_claims.append({
            "claim_text": claim,
            "is_temporal": True,  # Data dashboard claims are typically temporal
            "category": "other",
        })
    elif unique_entities:
        entity = unique_entities[0]
        # Check what metrics might be included; look for any numeric indicators
        if any(word in compact.lower() for word in ["gdp", "growth", "population", "income"]):
            claim = f"Statistical data about {entity} is available on this page."
            generated_claims.append({
                "claim_text": claim,
                "is_temporal": True,
                "category": "other",
            })
    elif unique_metrics:
        metric = unique_metrics[0]
        claim = f"This page provides {metric.lower()} data."
        generated_claims.append({
            "claim_text": claim,
            "is_temporal": True,
            "category": "other",
        })

    # Fallback: if compact is short and non-boilerplate, use raw compact text
    if not generated_claims and len(compact) > 10 and len(compact) < 150:
        clean = compact.replace("|", " ").replace("-", " ").strip()
        if len(clean) > 10:
            synthesized = clean.rstrip(".") + "."
            generated_claims.append({
                "claim_text": synthesized,
                "is_temporal": _is_temporal_claim(synthesized),
                "category": "other",
            })

    return generated_claims if generated_claims else []


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
    # Entity: allow both capitalized proper nouns AND lowercase references to countries/regions
    has_entity = bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", claim_text))
    
    # Concrete nouns that indicate verifiable claims (economy, sector, ranking, country, etc.)
    concrete_nouns = [
        "economy", "sector", "country", "nation", "world", "continent", "region",
        "company", "organization", "rank", "ranking", "position", "place",
        "gdp", "revenue", "growth", "population", "area", "capital", "healthcare", "accessibility", "poverty", "challenge", "challenges",
    ]
    has_concrete_noun = any(noun in lowered for noun in concrete_nouns)

    # Keep claims with concrete anchors: a number/date or named entities/concrete nouns plus factual verbs.
    factual_verbs = [
        "is", "was", "were", "became", "reported", "reports", "announced", "overtook",
        "ranked", "reached", "has", "have", "had", "shows", "show", "indicates", "indicate", "faces", "face", "faced",
        "use", "uses", "used",
    ]
    has_factual_verb = any(f" {v} " in f" {lowered} " for v in factual_verbs)
    return (has_number or has_date or has_entity or has_concrete_noun) and has_factual_verb


def _extract_subject_fragment(text: str) -> str:
    match = re.search(r"^\s*(.+?)\s+\b(is|are|was|were|has|have|had|became|become|can|could|may|might|will|would|should|must|faces|face|faced|leads|lead|causes|cause)\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip(" ,.-")


def _has_clause_verb(text: str) -> bool:
    lowered = (text or "").lower()
    return bool(re.search(r"\b(is|are|was|were|has|have|had|can|could|may|might|will|would|should|must|do|does|did|lead|leads|cause|causes|caused|show|shows|shown|indicate|indicates|face|faces|faced|remain|remains|became|become)\b", lowered))


def _split_compound_claim(sentence: str) -> List[str]:
    base = sentence.strip()
    if not base:
        return []

    # Normalize contrast connectives so they split consistently.
    base = re.sub(r"^\s*however,?\s+", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\s*,?\s*however,?\s+", " but ", base, flags=re.IGNORECASE)

    # Split conservatively: always split on "but"; split on "and" only if both sides look clause-like.
    chunks: List[str] = []
    cursor = 0
    for m in re.finditer(r"\s+(and|but)\s+", base, flags=re.IGNORECASE):
        conj = m.group(1).lower()
        left = base[cursor:m.start()].strip(" ,")
        right_preview = base[m.end():].strip(" ,")

        split_here = False
        if conj == "but":
            split_here = True
        elif conj == "and":
            if _has_clause_verb(left) and _has_clause_verb(right_preview) and not right_preview.lower().startswith(("other ", "another ")):
                split_here = True

        if split_here and left:
            chunks.append(left)
            cursor = m.end()

    tail = base[cursor:].strip(" ,")
    if tail:
        chunks.append(tail)

    parts = chunks if chunks else [base]
    if len(parts) <= 1:
        return [base]

    subject = _extract_subject_fragment(parts[0])
    claims: List[str] = []

    for idx, part in enumerate(parts):
        normalized = part.strip().rstrip(".")
        normalized = re.sub(r"^(but|however)\b\s*", "", normalized, flags=re.IGNORECASE).strip()
        if idx > 0 and subject:
            lowered = normalized.lower()
            # If fragment starts with pronoun, replace with subject
            if lowered.startswith(("it ", "they ", "this ", "that ")):
                # Extract the predicate part (everything after the pronoun + verb)
                predicate = re.sub(r"^(it|they|this|that)\s+(is|are|was|were|has|have|had|'s|'re|'d)\s+", "", lowered, flags=re.IGNORECASE)
                if predicate:
                    normalized = f"{subject} {' '.join(normalized.split()[1:])}"
                else:
                    normalized = f"{subject} {normalized}"
            elif not re.search(r"\b(is|are|was|were|has|have|had|can|could|may|might|will|would|should|must|became|ranked|reached|reported|announced|overtook|lead|leads|cause|causes|face|faces|faced|remain|remains)\b", lowered):
                # Fragment has no linking verb, so attach subject + "is" or "has"
                    # Skip low-quality fragments instead of fabricating missing grammar.
                    continue
            else:
                # Has a verb: prepend subject only when fragment begins with a predicate token
                # such as "is ...", "was ...", "has ..." where subject is clearly omitted.
                if re.match(r"^(is|are|was|were|has|have|had|can|could|may|might|will|would|should|must|faces|face|faced|leads|lead|causes|cause|shows|show|indicates|indicate)\b", lowered):
                    normalized = f"{subject} {normalized}"

        claims.append(normalized.strip() + ".")

    return claims


def _is_grounded_in_source(claim_text: str, source_text: str) -> bool:
    source_lower = (source_text or "").lower()
    claim_lower = (claim_text or "").lower().strip()
    if not source_lower or not claim_lower:
        return False

    # Numeric claims must preserve source numbers to avoid semantic drift
    # (e.g., model inventing "2-3 years" when input claim says "150 years").
    claim_numbers = re.findall(r"\d+(?:\.\d+)?", claim_lower)
    if claim_numbers and not all(num in source_lower for num in claim_numbers):
        return False

    # Strong signal: exact phrase appears in source.
    if claim_lower in source_lower:
        return True

    # Semantic matching: check for key concept overlap
    # Extract key content words (nouns, verbs, numbers), exclude stop words
    stop_words = {"is", "was", "are", "were", "has", "have", "had", "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for"}
    claim_tokens = [t for t in re.findall(r"[a-z0-9']+", claim_lower) if len(t) > 2 and t not in stop_words]
    source_tokens = [t for t in re.findall(r"[a-z0-9']+", source_lower) if len(t) > 2 and t not in stop_words]
    
    if not claim_tokens:
        return True  # Empty claims after filtering are considered sourced
    
    # Check keyword overlap: require 50% of content words to appear in source
    # This allows paraphrasing while preventing complete hallucination
    overlap = sum(1 for t in claim_tokens if any(t in st or st in t for st in source_tokens))
    overlap_ratio = overlap / len(claim_tokens) if claim_tokens else 1.0
    return overlap_ratio >= 0.50

async def extract_claims(text: str) -> List[Dict]:
    """
    Extract atomic, verifiable claims from the input text.
    Uses Chain-of-Thought prompting for accuracy.
    """
    # For short direct user input, prioritize deterministic extraction to preserve
    # the user's original statements and avoid LLM rewriting/drift.
    sentence_count = len([s for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()])
    primary_entity = _extract_primary_entity(text)
    direct_claims = _rule_based_claim_fallback(text)
    if FAST_PIPELINE_MODE and direct_claims:
        return direct_claims[:6]
    if len((text or "").strip()) <= 1200 and sentence_count <= 8 and direct_claims:
        return direct_claims[:10]

    prompt = f"""You are an expert fact-checking analyst. Your task is to extract ATOMIC, VERIFIABLE FACTUAL CLAIMS from the following text.

CRITICAL RULES:
1. Extract EVERY objective, factual statement that can be verified with evidence
2. Break compound statements (connected by "and", "but", etc.) into separate claims
3. Each claim must be a single, self-contained statement  
4. Skip ONLY opinions, predictions, and subjective statements
5. Preserve the exact meaning and context
6. Mark if a claim is TEMPORAL (time-sensitive, e.g., "currently", "as of 2024", involves a date/year)
7. Prioritize measurable claims with dates, counts, rankings, named entities, events, and official statements
8. Ignore ONLY vague/general descriptions that cannot be directly verified
9. Extract ALL verifiable claims, not just a subset

IMPORTANT: If the input contains multiple separate claims (especially connected by "and" or "but"), extract each one individually.
For example: "The economy grew and unemployment fell" should be TWO claims:
  - "The economy grew"
  - "Unemployment fell"

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

    try:
        response = await call_gemini(prompt)
        claims_data = extract_json_from_text(response)
    except Exception:
        return _rule_based_claim_fallback(text)

    if isinstance(claims_data, list):
        valid = []
        for claim in claims_data:
            if not isinstance(claim, dict):
                continue
            raw_claim_text = str(claim.get("claim_text", "")).strip()
            for claim_text in _split_compound_claim(raw_claim_text):
                claim_text = claim_text.strip()
                claim_text = _normalize_claim_spacing(claim_text)
                claim_text = _resolve_leading_pronoun(claim_text, primary_entity)
                if len(claim_text) < 20:
                    continue

                if not _is_structurally_sound_claim(claim_text):
                    continue
                if not _is_structurally_sound_claim(claim_text):
                    continue
                if _is_speculative_claim(claim_text):
                    continue
                if _is_low_value_metadata_claim(claim_text):
                    continue
                if not _looks_verifiable(claim_text):
                    continue
                if not _is_grounded_in_source(claim_text, text):
                    continue
                valid.append({
                    "claim_text": claim_text,
                    "is_temporal": bool(claim.get("is_temporal", False)) or _is_temporal_claim(claim_text),
                    "category": str(claim.get("category", "other")),
                    "priority": _claim_priority(claim_text),
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
            deduped.sort(key=lambda c: c.get("priority", 1), reverse=True)
            for c in deduped:
                c.pop("priority", None)
            return deduped[:10]

    return _rule_based_claim_fallback(text)

async def extract_claims_from_url(url: str) -> tuple[str, List[Dict]]:
    """Scrape URL and extract claims from its content."""
    content = await scrape_url(url)
    if not content:
        raise ValueError(f"Could not scrape content from URL: {url}")
    claims = await extract_claims(content)
    return content, claims
