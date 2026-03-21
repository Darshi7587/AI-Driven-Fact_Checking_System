from duckduckgo_search import DDGS
from typing import List, Dict
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
import time

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Search the web using DuckDuckGo with retry logic."""
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
                time.sleep(0.2)
    except Exception as e:
        print(f"Search error for '{query}': {e}")
    return results

async def search_web_async(query: str, max_results: int = 5) -> List[Dict]:
    """Async wrapper for web search."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: search_web(query, max_results))

async def multi_search(queries: List[str], max_results: int = 3) -> List[Dict]:
    """Search multiple queries and deduplicate results."""
    all_results = []
    seen_urls = set()
    for query in queries:
        results = await search_web_async(query, max_results)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)
        await asyncio.sleep(0.5)  # Rate limit respect
    return all_results
