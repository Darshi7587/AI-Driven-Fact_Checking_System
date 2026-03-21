import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import Optional
import re

TRUST_DOMAINS = {
    "reuters.com": 95, "apnews.com": 95, "bbc.com": 92, "bbc.co.uk": 92,
    "nytimes.com": 90, "washingtonpost.com": 88, "theguardian.com": 88,
    "npr.org": 90, "pbs.org": 88, "economist.com": 90, "nature.com": 95,
    "science.org": 95, "pubmed.ncbi.nlm.nih.gov": 97, "who.int": 95,
    "cdc.gov": 95, "nih.gov": 95, "gov": 85, "edu": 85,
    "wikipedia.org": 70, "snopes.com": 80, "factcheck.org": 85,
    "politifact.com": 82, "fullfact.org": 83, "bloomberg.com": 87,
    "forbes.com": 78, "techcrunch.com": 75, "wired.com": 78,
    "medium.com": 45, "substack.com": 40, "reddit.com": 30,
    "twitter.com": 25, "x.com": 25, "facebook.com": 20
}

def get_trust_score(url: str) -> float:
    """Score domain trustworthiness 0-100."""
    domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
    for trusted_domain, score in TRUST_DOMAINS.items():
        if trusted_domain in domain:
            return score / 100.0
    # Default for unknown domains
    if ".gov" in domain:
        return 0.85
    if ".edu" in domain:
        return 0.82
    if ".org" in domain:
        return 0.60
    return 0.50

async def scrape_url(url: str, timeout: int = 10) -> Optional[str]:
    """Scrape text content from a URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return None
            soup = BeautifulSoup(response.text, "lxml")
            # Remove script/style tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            # Extract main content
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50)
            return text[:3000] if text else None
    except Exception:
        return None

def extract_domain(url: str) -> str:
    domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
    return domain
