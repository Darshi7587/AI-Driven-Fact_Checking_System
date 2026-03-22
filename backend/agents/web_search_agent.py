from services.gemini_service import call_gemini, extract_json_from_text
from services.scraper_service import get_trust_score, extract_domain, get_preview_image_url
from services.search_service import multi_search
from typing import List, Dict
import asyncio
from config import MAX_SEARCH_RESULTS_PER_QUERY

async def search_and_collect_evidence(claim: str, queries: List[str]) -> List[Dict]:
    """
    Search for evidence and collect structured source data.
    """
    raw_results = await multi_search(queries, max_results=max(2, MAX_SEARCH_RESULTS_PER_QUERY))
    
    evidence_sources = []
    for result in raw_results:
        url = result.get("url", "")
        title = result.get("title", "Unknown Title")
        snippet = result.get("snippet", "")
        
        if not url or not snippet:
            continue
        
        trust_score = get_trust_score(url)
        domain = extract_domain(url)
        
        evidence_sources.append({
            "url": url,
            "title": title,
            "snippet": snippet,
            "trust_score": trust_score,
            "domain": domain,
            "image_url": None,
        })
    
    # Sort by trust score descending
    evidence_sources.sort(key=lambda x: x["trust_score"], reverse=True)

    top_sources = evidence_sources[:5]  # Keep top sources compact for speed and quality

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

    return final_sources
