import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import Optional
import re
from urllib.parse import urljoin
from urllib.parse import unquote, urlparse

HIGH_TRUST_DOMAINS = {
    # Global news
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bbc.com": 0.92,
    "bbc.co.uk": 0.92,
    "nytimes.com": 0.90,
    "theguardian.com": 0.88,
    # India trusted
    "thehindu.com": 0.88,
    "indianexpress.com": 0.86,
    "pib.gov.in": 0.96,
    # Government and institutions
    "nasa.gov": 0.96,
    "who.int": 0.95,
    "un.org": 0.95,
    "worldbank.org": 0.92,
    "imf.org": 0.92,
    # Scientific and academic
    "nature.com": 0.95,
    "sciencedirect.com": 0.93,
    "ncbi.nlm.nih.gov": 0.97,
    "pubmed.ncbi.nlm.nih.gov": 0.97,
    "science.org": 0.95,
    "cdc.gov": 0.95,
    "nih.gov": 0.95,
}

MEDIUM_TRUST_DOMAINS = {
    "congress.gov": 0.78,
    "wikipedia.org": 0.70,
    "snopes.com": 0.80,
    "factcheck.org": 0.85,
    "politifact.com": 0.82,
    "fullfact.org": 0.83,
    "forbes.com": 0.78,
    "businessinsider.com": 0.74,
    "techcrunch.com": 0.75,
    "wired.com": 0.78,
    "timesofindia.indiatimes.com": 0.72,
    "ndtv.com": 0.74,
    "hindustantimes.com": 0.73,
    "medium.com": 0.45,
    "towardsdatascience.com": 0.52,
    "dev.to": 0.48,
}

LOW_TRUST_DOMAINS = {
    "substack.com": 0.40,
    "reddit.com": 0.30,
    "twitter.com": 0.25,
    "x.com": 0.25,
    "facebook.com": 0.20,
    "blogspot.com": 0.30,
}

LOW_TRUST_TLDS = {".xyz", ".buzz", ".click", ".top", ".gq", ".work"}
LOW_TRUST_TOKENS = {
    "viral", "truthnews", "breaking-news", "worldtruth", "dailynews247", "exposed", "uncensored"
}


def _domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
    except Exception:
        host = url
    host = host.lower().strip()
    host = re.sub(r"^https?://", "", host)
    host = re.sub(r"^www\.", "", host)
    host = host.split("/")[0]
    return host


def _lookup_domain_score(domain: str, domain_map: dict[str, float]) -> float | None:
    for trusted_domain, score in domain_map.items():
        if domain == trusted_domain or domain.endswith(f".{trusted_domain}"):
            return score
    return None

def get_trust_score(url: str) -> float:
    """Score domain trustworthiness from 0.0 to 1.0 using curated + dynamic rules."""
    domain = _domain_from_url(url)

    score = _lookup_domain_score(domain, HIGH_TRUST_DOMAINS)
    if score is not None:
        return score

    score = _lookup_domain_score(domain, MEDIUM_TRUST_DOMAINS)
    if score is not None:
        return score

    score = _lookup_domain_score(domain, LOW_TRUST_DOMAINS)
    if score is not None:
        return score

    # Dynamic signals for unknown domains.
    lowered = domain.lower()
    if any(lowered.endswith(tld) for tld in LOW_TRUST_TLDS):
        return 0.25
    if any(token in lowered for token in LOW_TRUST_TOKENS):
        return 0.30

    # Institutional defaults.
    if lowered.endswith(".gov") or lowered.endswith(".gov.in"):
        return 0.88
    if lowered.endswith(".edu") or lowered.endswith(".ac.in"):
        return 0.84
    if lowered.endswith(".org"):
        return 0.62

    # Generic default for unknown commercial/news domains.
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
