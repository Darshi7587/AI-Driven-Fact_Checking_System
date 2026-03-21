from services.gemini_service import call_gemini, extract_json_from_text
from services.scraper_service import get_trust_score, extract_domain
from services.search_service import multi_search
from typing import List, Dict
import asyncio

async def search_and_collect_evidence(claim: str, queries: List[str]) -> List[Dict]:
    """
    Search for evidence and collect structured source data.
    """
    raw_results = await multi_search(queries, max_results=4)
    
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
            "domain": domain
        })
    
    # Sort by trust score descending
    evidence_sources.sort(key=lambda x: x["trust_score"], reverse=True)
    return evidence_sources[:6]  # Top 6 sources
