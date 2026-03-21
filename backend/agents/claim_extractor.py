from services.gemini_service import call_gemini, extract_json_from_text
from services.scraper_service import scrape_url
from typing import List, Dict
import json

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
6. Extract 3-10 most important verifiable claims

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
        return claims_data
    return []

async def extract_claims_from_url(url: str) -> tuple[str, List[Dict]]:
    """Scrape URL and extract claims from its content."""
    content = await scrape_url(url)
    if not content:
        raise ValueError(f"Could not scrape content from URL: {url}")
    claims = await extract_claims(content)
    return content, claims
