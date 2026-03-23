import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import Optional
import re
from urllib.parse import urljoin
from urllib.parse import unquote, urlparse

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
            boilerplate_tokens = [
                "this site uses cookies",
                "cookies will be placed",
                "privacy policy",
                "accept cookies",
                "cookie",
                "javascript",
            ]

            candidates = []
            for p in paragraphs:
                p_text = p.get_text(strip=True)
                if len(p_text) <= 50:
                    continue
                lowered = p_text.lower()
                if any(token in lowered for token in boilerplate_tokens):
                    continue
                candidates.append(p_text)

            text = " ".join(candidates)

            if text:
                return text[:3000]

            # Fallback for JS-heavy dashboards/data pages with sparse paragraph text.
            title = (soup.title.get_text(strip=True) if soup.title else "")
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag.get("content", "").strip()

            headings = []
            for h in soup.find_all(["h1", "h2"], limit=5):
                h_text = h.get_text(" ", strip=True)
                if h_text and len(h_text) >= 8:
                    headings.append(h_text)

            parsed = urlparse(str(response.url))
            path_hint = unquote(parsed.path or "")
            query_hint = unquote(parsed.query or "")

            url_hint = ""
            if path_hint or query_hint:
                compact_path = re.sub(r"[/_-]+", " ", path_hint).strip()
                compact_query = re.sub(r"[=&_-]+", " ", query_hint).strip()
                # Only include URL hint if it has meaningful info (not just indicator=...); skip redundant query params
                if len(compact_query.split()) <= 3:  # "NY GDP MKTP CD" is ok, "Selected Countries Economies" is boilerplate
                    url_hint = f"URL: {compact_path} {compact_query}".strip() if compact_path else ""

            # Clean fallback parts: remove empty, deduplicate, respect order
            fallback_parts = []
            for part in [title, meta_desc, " ".join(headings[:2])]:
                if part and part not in fallback_parts:
                    fallback_parts.append(part)
            if url_hint:
                fallback_parts.append(url_hint)
            
            fallback_text = " ".join(fallback_parts).strip()
            return fallback_text[:2000] if fallback_text else None
    except Exception:
        return None


async def extract_media_urls(url: str, timeout: int = 10, max_items: int = 12) -> list[dict]:
    """Extract image/audio/video URLs from a page for media integrity analysis."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return []
            soup = BeautifulSoup(response.text, "lxml")
    except Exception:
        return []

    media = []

    def add_media(media_type: str, raw_url: str):
        if not raw_url:
            return
        absolute = urljoin(url, raw_url)
        if not absolute.startswith("http"):
            return
        media.append({"type": media_type, "url": absolute})

    for tag in soup.find_all("img"):
        add_media("image", tag.get("src") or tag.get("data-src") or tag.get("srcset"))

    for tag in soup.find_all("audio"):
        add_media("audio", tag.get("src"))
        for source in tag.find_all("source"):
            add_media("audio", source.get("src"))

    for tag in soup.find_all("video"):
        add_media("video", tag.get("src"))
        for source in tag.find_all("source"):
            add_media("video", source.get("src"))

    # Deduplicate while preserving order.
    seen = set()
    deduped = []
    for item in media:
        key = f"{item['type']}::{item['url']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max_items:
            break

    return deduped


async def get_preview_image_url(url: str, timeout: int = 6) -> Optional[str]:
    """Best-effort extraction of a representative preview image URL for a page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return None
            soup = BeautifulSoup(response.text, "lxml")
    except Exception:
        return None

    # Prioritize standard social preview tags.
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return urljoin(url, og.get("content"))

    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        return urljoin(url, tw.get("content"))

    # Fallback to first non-trivial image on the page.
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        absolute = urljoin(url, src)
        lowered = absolute.lower()
        if any(x in lowered for x in ["sprite", "logo", "icon", "avatar"]):
            continue
        if absolute.startswith("http"):
            return absolute

    return None

def extract_domain(url: str) -> str:
    domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
    return domain
