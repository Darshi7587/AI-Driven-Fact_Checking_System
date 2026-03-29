from services.gemini_service import call_gemini, extract_json_from_text
from services.scraper_service import get_trust_score, extract_domain, get_preview_image_url
from services.search_service import multi_search
from typing import List, Dict
import asyncio
import re
from config import MAX_SEARCH_RESULTS_PER_QUERY, FAST_PIPELINE_MODE, FAST_MAX_SEARCH_RESULTS_PER_QUERY


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _claim_keywords(claim: str) -> List[str]:
    text = _normalize(claim)
    tokens = re.findall(r"[a-z0-9']+", text)
    stop = {
        "the", "a", "an", "and", "or", "but", "is", "was", "were", "are", "has", "have", "had",
        "to", "for", "in", "on", "at", "of", "with", "by", "its", "it", "this", "that", "all", "from",
        "as", "be", "been", "being", "about", "around", "approximately", "latest", "data", "official", "source",
    }
    return [t for t in tokens if len(t) > 2 and t not in stop]


def _named_entities(claim: str) -> List[str]:
    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", claim or "")
    stop = {"The", "This", "That", "These", "Those", "It", "He", "She", "They", "In", "On", "At"}
    unique = []
    seen = set()
    for e in entities:
        token = e.strip()
        if token in stop:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(token)
    return unique[:4]


def _has_entity_alignment(claim: str, source_text: str) -> bool:
    entities = _named_entities(claim)
    if not entities:
        return True
    text = _normalize(source_text)
    return any(_normalize(entity) in text for entity in entities)


def _anchor_aliases_for_claim(claim: str) -> List[List[str]]:
    text = _normalize(claim)
    anchors: List[List[str]] = []
    if any(k in text for k in ["landed", "landing", "land on", "moon landing", "successfully landed"]):
        anchors.append(["landed", "landing", "touchdown", "touch down", "soft-landing", "soft landing"])
    if any(k in text for k in ["launched", "launch"]):
        anchors.append(["launch", "launched", "lift-off", "liftoff"])
    if any(k in text for k in ["approved", "approval", "authorized", "endorsed"]):
        anchors.append(["approved", "approval", "authorized", "endorsed", "cleared"])
    return anchors


def _required_phrase_groups(claim: str) -> List[List[str]]:
    text = _normalize(claim)
    groups: List[List[str]] = []

    # Versioned model claims (e.g., GPT-5) require direct model mention in source text.
    gpt_match = re.search(r"\bgpt\s*[- ]?(\d+(?:\.\d+)?)\b", text)
    if gpt_match:
        version = gpt_match.group(1)
        groups.append([f"gpt-{version}", f"gpt {version}", f"gpt{version}"])

    return groups


def _keyword_overlap_ratio(claim: str, source_text: str) -> float:
    keywords = _claim_keywords(claim)
    if not keywords:
        return 0.0
    text = _normalize(source_text)
    match_count = sum(1 for kw in keywords if kw in text)
    return match_count / len(keywords)


def _passes_anchor_check(claim: str, source_text: str) -> bool:
    anchors = _anchor_aliases_for_claim(claim)
    if not anchors:
        return True
    text = _normalize(source_text)
    for alias_group in anchors:
        if not any(alias in text for alias in alias_group):
            return False

    required_groups = _required_phrase_groups(claim)
    for req_group in required_groups:
        if not any(req in text for req in req_group):
            return False

    return True


def _relevance_score(claim: str, title: str, snippet: str) -> float:
    combined = f"{title}. {snippet}"
    overlap = _keyword_overlap_ratio(claim, combined)
    anchor_bonus = 0.2 if _passes_anchor_check(claim, combined) else -0.25
    entity_bonus = 0.12 if _has_entity_alignment(claim, combined) else -0.18
    return max(0.0, min(1.0, overlap + anchor_bonus + entity_bonus))


def _authority_boost_queries(claim: str) -> List[str]:
    text = _normalize(claim)
    base = []
    if any(k in text for k in ["war", "ceasefire", "truce", "conflict", "israel", "iran", "russia", "ukraine", "gaza", "hamas"]):
        base.extend([
            f"{claim} site:reuters.com",
            f"{claim} site:apnews.com",
            f"{claim} site:bbc.com",
            f"{claim} site:aljazeera.com",
        ])
        return base
    if any(k in text for k in ["chandrayaan", "isro", "moon", "lunar"]):
        base.extend([
            f"{claim} site:isro.gov.in",
            f"{claim} site:bbc.com",
            f"{claim} site:reuters.com",
        ])
    elif any(k in text for k in ["economy", "gdp", "inflation", "growth"]):
        base.extend([
            f"{claim} site:worldbank.org",
            f"{claim} site:imf.org",
            f"{claim} site:reuters.com",
        ])
    elif any(k in text for k in ["health", "vaccine", "virus", "disease", "medical"]):
        base.extend([
            f"{claim} site:who.int",
            f"{claim} site:cdc.gov",
            f"{claim} site:reuters.com",
        ])
    else:
        base.extend([
            f"{claim} site:reuters.com",
            f"{claim} site:bbc.com",
        ])
    return base

async def search_and_collect_evidence(claim: str, queries: List[str]) -> List[Dict]:
    """
    Search for evidence and collect structured source data.
    """
    max_results = FAST_MAX_SEARCH_RESULTS_PER_QUERY if FAST_PIPELINE_MODE else MAX_SEARCH_RESULTS_PER_QUERY
    raw_results = await multi_search(queries[:2] if FAST_PIPELINE_MODE else queries, max_results=max(2, max_results))
    
    evidence_sources = []
    for result in raw_results:
        url = result.get("url", "")
        title = result.get("title", "Unknown Title")
        snippet = result.get("snippet", "")
        
        if not url or not snippet:
            continue
        
        trust_score = get_trust_score(url)
        domain = extract_domain(url)
        relevance = _relevance_score(claim, title, snippet)

        # Hard relevance gate: drop weak/irrelevant snippets early.
        if relevance < 0.22:
            continue

        # If claim contains event anchors like "landed", enforce direct lexical relevance.
        if not _passes_anchor_check(claim, f"{title}. {snippet}"):
            continue

        if not _has_entity_alignment(claim, f"{title}. {snippet}"):
            continue
        
        evidence_sources.append({
            "url": url,
            "title": title,
            "snippet": snippet,
            "trust_score": trust_score,
            "domain": domain,
            "relevance_score": relevance,
            "image_url": None,
        })

    # If we still lack relevant sources, run a targeted second pass for authoritative domains.
    if (not FAST_PIPELINE_MODE) and len(evidence_sources) < 3:
        boosted_queries = _authority_boost_queries(claim)
        boosted_results = await multi_search(boosted_queries, max_results=max(2, MAX_SEARCH_RESULTS_PER_QUERY))
        seen_urls = {s["url"] for s in evidence_sources}
        for result in boosted_results:
            url = result.get("url", "")
            title = result.get("title", "Unknown Title")
            snippet = result.get("snippet", "")
            if not url or not snippet or url in seen_urls:
                continue

            relevance = _relevance_score(claim, title, snippet)
            if relevance < 0.22 or not _passes_anchor_check(claim, f"{title}. {snippet}"):
                continue
            if not _has_entity_alignment(claim, f"{title}. {snippet}"):
                continue

            seen_urls.add(url)
            evidence_sources.append(
                {
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "trust_score": get_trust_score(url),
                    "domain": extract_domain(url),
                    "relevance_score": relevance,
                    "image_url": None,
                }
            )

    # Rank by combined quality score so relevance dominates trust.
    evidence_sources.sort(
        key=lambda x: ((0.65 * x.get("relevance_score", 0.0)) + (0.35 * x["trust_score"])),
        reverse=True,
    )

    # Ensure at least one high-trust source is included when available.
    high_trust_candidates = [s for s in evidence_sources if s.get("trust_score", 0.0) >= 0.85]
    selected = []
    if high_trust_candidates:
        selected.append(high_trust_candidates[0])
        selected_urls = {high_trust_candidates[0]["url"]}
    else:
        selected_urls = set()

    for src in evidence_sources:
        if src["url"] in selected_urls:
            continue
        selected.append(src)
        selected_urls.add(src["url"])
        if len(selected) >= 5:
            break

    top_sources = selected[:3] if FAST_PIPELINE_MODE else selected[:5]  # Keep top sources compact for speed and quality

    if FAST_PIPELINE_MODE:
        for src in top_sources:
            src.pop("relevance_score", None)
        return top_sources

    semaphore = asyncio.Semaphore(3)

    async def attach_preview(source: Dict):
        async with semaphore:
            source["image_url"] = await get_preview_image_url(source["url"])
            return source

    enriched = await asyncio.gather(*(attach_preview(s) for s in top_sources), return_exceptions=True)

    final_sources = []
    for i, item in enumerate(enriched):
        if isinstance(item, Exception):
            final_sources.append(top_sources[i])
        else:
            final_sources.append(item)

    for src in final_sources:
        src.pop("relevance_score", None)

    return final_sources
