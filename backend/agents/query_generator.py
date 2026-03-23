from services.gemini_service import call_gemini, extract_json_from_text
from typing import List, Dict
import re


def _detect_claim_type(claim: str) -> str:
    lowered = claim.lower()
    if any(k in lowered for k in ["coffee", "caffeine"]) and any(k in lowered for k in ["benefit", "anxiety", "sleep", "insomnia", "excessive intake", "health issue"]):
        return "caffeine_effects"
    if any(k in lowered for k in ["located in", "consists of", "comprises", "states", "continents"]):
        return "geography_fact"
    if any(k in lowered for k in ["boils at", "freezes at", "degrees celsius", "standard atmospheric pressure"]):
        return "physical_science"
    if any(k in lowered for k in ["revolves around the sun", "orbits the sun", "one orbit", "365 days"]):
        return "astronomy_orbit"
    if "most populous" in lowered or "population" in lowered:
        return "population"
    if "gdp" in lowered or "econom" in lowered or "largest economies" in lowered:
        return "gdp"
    if "poverty" in lowered:
        return "poverty"
    if "healthcare" in lowered or "health care" in lowered:
        return "healthcare"
    if "information technology" in lowered or "it sector" in lowered or "it services" in lowered or "tech" in lowered:
        return "it_sector"
    return "general"


def _extract_main_entity(claim: str) -> str:
    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", claim)
    for ent in entities:
        if ent.lower() in {"it", "this", "that", "they", "these", "those"}:
            continue
        return ent
    return "country"


def _extract_focus_terms(claim: str, limit: int = 6) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9']+", (claim or "").lower())
    stop = {
        "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "to", "of", "in", "on", "for",
        "with", "by", "at", "from", "it", "this", "that", "these", "those", "as", "also", "one",
    }
    terms = [t for t in tokens if len(t) > 2 and t not in stop]
    # Keep order, drop duplicates
    unique = []
    seen = set()
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
        if len(unique) >= limit:
            break
    return unique


def _generic_fallback_queries(claim: str) -> List[str]:
    entity = _extract_main_entity(claim)
    focus_terms = _extract_focus_terms(claim)
    focus = " ".join(focus_terms) if focus_terms else claim
    base = re.sub(r"\s+", " ", (claim or "").strip())

    q1 = f"{entity} {focus} official source" if entity != "country" else f"{focus} official source"
    q2 = f"{focus} site:gov OR site:edu OR site:org"
    q3 = f"fact check {focus} Reuters AP BBC"

    # Avoid overlong or empty queries
    cleaned = []
    for q in [q1, q2, q3]:
        q = re.sub(r"\s+", " ", q).strip()
        if not q:
            continue
        if len(q) > 180:
            q = q[:180].rsplit(" ", 1)[0]
        cleaned.append(q)

    if len(cleaned) >= 3:
        return cleaned[:3]

    return [
        f"{base} latest data official source",
        f"{base} site:gov OR site:edu OR site:org",
        f"fact check {base}",
    ]


def _with_seed_query(claim: str, queries: List[str]) -> List[str]:
    seed = re.sub(r"\s+", " ", f"{claim} official data latest").strip()
    merged = [seed]
    merged.extend(queries or [])
    unique = []
    seen = set()
    for q in merged:
        key = q.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(q.strip())
    return unique[:3]


def _sanitize_query(query: str, claim: str, entity: str) -> str:
    q = (query or "").strip()
    if not q:
        return ""

    replacements = {
        "[entity name]": entity,
        "[official source]": "official source",
        "[year]": "latest",
    }
    lower_q = q.lower()
    for token, replacement in replacements.items():
        if token in lower_q:
            pattern = re.compile(re.escape(token), flags=re.IGNORECASE)
            q = pattern.sub(replacement, q)

    # If placeholder brackets still exist, degrade to a safe explicit query.
    if "[" in q or "]" in q:
        return f"{entity} {claim} latest data official source"

    return re.sub(r"\s+", " ", q).strip()


def _fallback_queries_for_claim(claim: str) -> List[str]:
    claim_type = _detect_claim_type(claim)
    entity = _extract_main_entity(claim)

    if claim_type == "population":
        return _with_seed_query(claim, [
            f"{entity} most populous country 2023 site:un.org",
            f"{entity} population ranking 2023 site:worldbank.org OR site:data.un.org",
            f"{entity} overtook China population UN DESA report",
        ])
    if claim_type == "geography_fact":
        return _with_seed_query(claim, [
            f"{claim} official source encyclopedia",
            f"{entity} country profile states location site:cia.gov OR site:britannica.com",
            f"{entity} located in which continent official reference",
        ])
    if claim_type == "physical_science":
        return _with_seed_query(claim, [
            "water boiling point celsius standard atmospheric pressure source",
            "water freezing point celsius scientific reference",
            "NIST water phase change temperature 1 atm",
        ])
    if claim_type == "astronomy_orbit":
        return _with_seed_query(claim, [
            "Earth revolves around Sun orbital period 365 days NASA",
            "Earth orbit duration around Sun scientific reference",
            "astronomical year length in days authoritative source",
        ])
    if claim_type == "caffeine_effects":
        return _with_seed_query(claim, [
            "coffee health benefits moderate intake evidence-based review",
            "excessive caffeine intake anxiety sleep disorders systematic review",
            "WHO NIH guidance caffeine daily intake and side effects",
        ])
    if claim_type == "gdp":
        return _with_seed_query(claim, [
            f"{entity} GDP current US$ site:worldbank.org",
            f"{entity} nominal GDP IMF World Economic Outlook",
            f"{entity} GDP trillion dollars official statistics",
        ])
    if claim_type == "poverty":
        return _with_seed_query(claim, [
            f"{entity} poverty rate latest data site:worldbank.org",
            f"{entity} multidimensional poverty index site:undp.org OR site:un.org",
            f"Has {entity} eliminated poverty official report",
        ])
    if claim_type == "healthcare":
        return _with_seed_query(claim, [
            f"{entity} universal healthcare coverage WHO profile",
            f"{entity} free healthcare for all citizens official policy",
            f"{entity} health insurance coverage latest data site:who.int OR site:worldbank.org",
        ])
    if claim_type == "it_sector":
        return _with_seed_query(claim, [
            f"{entity} global leader IT services exports",
            f"{entity} software services ranking global",
            f"{entity} information technology services market share report",
        ])

    return _with_seed_query(claim, _generic_fallback_queries(claim))

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

    try:
        response = await call_gemini(prompt)
        data = extract_json_from_text(response)
    except Exception:
        return _fallback_queries_for_claim(claim)
    entity = _extract_main_entity(claim)
    
    if isinstance(data, dict) and "queries" in data:
        raw_queries = [q.strip() for q in data["queries"] if isinstance(q, str) and q.strip()]
        unique_queries = []
        seen = set()
        for q in raw_queries:
            q = _sanitize_query(q, claim, entity)
            if not q:
                continue
            key = q.lower()
            if key not in seen:
                seen.add(key)
                unique_queries.append(q)
        if len(unique_queries) >= 3:
            return unique_queries[:3]
    
    return _fallback_queries_for_claim(claim)
