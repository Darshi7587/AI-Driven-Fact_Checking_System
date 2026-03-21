from services.gemini_service import call_gemini, extract_json_from_text
from typing import Dict

async def detect_hallucination(claim: str, verification_result: Dict, evidence_sources: list) -> Dict:
    """
    Specialized agent to detect if a claim is an LLM hallucination.
    Analyzes patterns that indicate AI-generated false information.
    """
    status = verification_result.get("status", "UNVERIFIABLE")
    confidence = verification_result.get("confidence", 0.5)
    
    # High-confidence FALSE with low source trust is hallucination suspect
    is_hallucination_suspect = (
        status == "FALSE" and confidence > 0.7 and
        len(evidence_sources) > 0 and
        all(s.get("trust_score", 0) > 0.7 for s in evidence_sources[:2])
    )
    
    hallucination_patterns = [
        any(phrase in claim.lower() for phrase in [
            "according to a study", "researchers found", "experts say",
            "scientists discovered", "a report states"
        ]),
        len(claim.split()) > 30,  # Very specific/long claims
        status == "UNVERIFIABLE" and confidence < 0.3,
    ]
    
    hallucination_score = sum(hallucination_patterns) / len(hallucination_patterns)
    is_hallucination = is_hallucination_suspect or hallucination_score > 0.5
    
    return {
        "is_hallucination": is_hallucination,
        "hallucination_score": round(hallucination_score, 2),
        "reason": "Claim contradicted by multiple authoritative sources with high confidence" if is_hallucination_suspect 
                  else "Pattern-based hallucination indicators detected" if is_hallucination 
                  else "No strong hallucination indicators"
    }

async def check_temporal_validity(claim: str, is_temporal: bool) -> Dict:
    """Check if a claim is temporally outdated."""
    if not is_temporal:
        return {"is_temporal_issue": False, "note": ""}
    
    prompt = f"""Is this claim TEMPORALLY SENSITIVE? Does it reference current state, recent events, or time-relative information?

Claim: "{claim}"

If temporally sensitive, flag it. Return JSON only:
{{
  "is_temporal_issue": true or false,
  "temporal_note": "Brief note about the temporal sensitivity (e.g., 'Claim references current CEO, may be outdated')"
}}"""
    
    response = await call_gemini(prompt)
    result = extract_json_from_text(response)
    if isinstance(result, dict):
        return result
    return {"is_temporal_issue": True, "temporal_note": "Claim contains time-sensitive information"}
