from services.gemini_service import call_gemini, extract_json_from_text
from typing import List, Dict

async def generate_search_queries(claim: str) -> List[str]:
    """
    Generate multiple diverse search queries for a claim to maximize evidence retrieval.
    """
    prompt = f"""You are a professional investigative journalist and fact-checker.

Given this CLAIM to verify: "{claim}"

Generate 3 DIFFERENT search queries that will find REAL, AUTHORITATIVE sources to verify or refute this claim.
- Query 1: Direct verification query
- Query 2: Counter-evidence / alternative perspective query  
- Query 3: Context/background query with key entities

Rules:
- Make queries specific and likely to return authoritative sources
- Use different angles/perspectives
- Include key entities, dates, numbers from the claim
- Prefer official/statistical sources (UN, World Bank, WHO, government, Reuters, AP, BBC)
- Add terms like "latest data", "official source", or "report" where appropriate

Return ONLY valid JSON (no markdown):
{{
  "queries": ["query 1", "query 2", "query 3"]
}}"""

    response = await call_gemini(prompt)
    data = extract_json_from_text(response)
    
    if isinstance(data, dict) and "queries" in data:
        raw_queries = [q.strip() for q in data["queries"] if isinstance(q, str) and q.strip()]
        unique_queries = []
        seen = set()
        for q in raw_queries:
            key = q.lower()
            if key not in seen:
                seen.add(key)
                unique_queries.append(q)
        if len(unique_queries) >= 3:
            return unique_queries[:3]
    
    # Fallback: create basic query from claim
    return [
        f"{claim} latest data official source",
        f"{claim} site:un.org OR site:worldbank.org OR site:who.int OR site:gov",
        f"fact check {claim} Reuters AP BBC",
    ]
