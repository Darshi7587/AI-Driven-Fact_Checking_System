from duckduckgo_search import DDGS
from typing import List, Dict
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx
from config import TAVILY_API_KEY, SEARCH_QUERY_CONCURRENCY

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
    except Exception as e:
        print(f"Search error for '{query}': {e}")
    return results

async def search_web_async(query: str, max_results: int = 5) -> List[Dict]:
    """Async wrapper for web search."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: search_web(query, max_results))

async def search_tavily(query: str, max_results: int = 5) -> List[Dict]:
    """Search with Tavily as primary provider when API key is configured."""
    if not TAVILY_API_KEY:
        return []

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        print(f"Tavily search error for '{query}': {e}")
        return []

    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "source_engine": "tavily",
        })
    return results

async def multi_search(queries: List[str], max_results: int = 3) -> List[Dict]:
    """Search multiple queries with Tavily primary and DuckDuckGo fallback."""
    if not queries:
        return []

    semaphore = asyncio.Semaphore(max(1, SEARCH_QUERY_CONCURRENCY))

    async def search_single_query(query: str) -> List[Dict]:
        async with semaphore:
            results = await search_tavily(query, max_results=max_results)
            if not results:
                results = await search_web_async(query, max_results)
            return results

    results_per_query = await asyncio.gather(*(search_single_query(q) for q in queries))

    all_results = []
    seen_urls = set()

    for results in results_per_query:
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)

    return all_results
