from services.gemini_service import call_gemini, extract_json_from_text
from typing import List, Dict
import json


def _safe_indices(values) -> List[int]:
    if not isinstance(values, list):
        return []
    parsed = []
    for v in values:
        try:
            idx = int(v)
            if idx > 0:
                parsed.append(idx)
        except Exception:
            continue
    return parsed


def _avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _compute_confidence(status: str, evidence_sources: List[Dict], supporting: List[int], contradicting: List[int]) -> float:
    total_sources = max(len(evidence_sources), 1)
    trust_by_index = {
        i + 1: float(src.get("trust_score", 0.5))
        for i, src in enumerate(evidence_sources)
    }

    support_trust = [trust_by_index[i] for i in supporting if i in trust_by_index]
    contradict_trust = [trust_by_index[i] for i in contradicting if i in trust_by_index]

    if status == "TRUE":
        evidence_count = len(support_trust)
        avg_credibility = _avg(support_trust)
    elif status == "FALSE":
        evidence_count = len(contradict_trust)
        avg_credibility = _avg(contradict_trust)
    elif status in {"PARTIALLY_TRUE", "CONFLICTING"}:
        evidence_count = max(len(support_trust), len(contradict_trust))
        avg_credibility = _avg(support_trust + contradict_trust)
    else:
        return 0.2

    confidence = (evidence_count * avg_credibility) / total_sources
    confidence = max(0.15, min(confidence, 0.98))
    return round(confidence, 3)


def _apply_credibility_upgrade_rules(result: Dict, evidence_sources: List[Dict], supporting: List[int], contradicting: List[int]) -> Dict:
    trust_by_index = {
        i + 1: float(src.get("trust_score", 0.5))
        for i, src in enumerate(evidence_sources)
    }

    support_trust = [trust_by_index[i] for i in supporting if i in trust_by_index]
    contradict_trust = [trust_by_index[i] for i in contradicting if i in trust_by_index]
    high_support = sum(1 for t in support_trust if t >= 0.85)
    high_contradict = sum(1 for t in contradict_trust if t >= 0.85)

    status = result.get("status", "UNVERIFIABLE")

    reasoning = f"{result.get('reasoning', '')} {result.get('key_finding', '')}".lower()
    uncertainty_tokens = [
        "unclear", "not clear", "no direct", "insufficient", "cannot verify", "might", "may", "overstatement",
        "not directly", "unknown", "remains unclear", "inconclusive",
    ]
    has_uncertainty = any(token in reasoning for token in uncertainty_tokens)

    # If 2+ trusted sources support and no trusted contradiction, upgrade cautious partial to true.
    if status == "PARTIALLY_TRUE" and high_support >= 2 and high_contradict == 0 and not has_uncertainty:
        result["status"] = "TRUE"
        result["conflicting_evidence"] = False

    # If trusted contradiction exists alongside support, keep as partial conflict.
    if support_trust and high_contradict >= 1:
        result["status"] = "PARTIALLY_TRUE"
        result["conflicting_evidence"] = True

    return result


def _normalize_uncertain_true(result: Dict, supporting: List[int]) -> Dict:
    status = result.get("status", "UNVERIFIABLE")
    reasoning = f"{result.get('reasoning', '')} {result.get('key_finding', '')}".lower()
    uncertainty_tokens = [
        "unclear", "not clear", "no direct", "insufficient", "cannot verify", "might", "may", "overstatement",
        "not directly", "unknown", "remains unclear", "inconclusive",
    ]
    has_uncertainty = any(token in reasoning for token in uncertainty_tokens)

    if status == "TRUE" and (has_uncertainty or not supporting):
        result["status"] = "PARTIALLY_TRUE" if supporting else "UNVERIFIABLE"
        result["conflicting_evidence"] = result.get("conflicting_evidence", False)

    return result

async def verify_claim(claim: str, evidence_sources: List[Dict]) -> Dict:
    """
    Core verification agent using Chain-of-Thought reasoning.
    Compares claim against retrieved evidence to determine truthfulness.
    """
    if not evidence_sources:
        return {
            "status": "UNVERIFIABLE",
            "confidence": 0.2,
            "reasoning": "No evidence sources found to verify this claim.",
            "conflicting_evidence": False
        }
    
    # Format evidence for prompt
    evidence_text = ""
    for i, src in enumerate(evidence_sources[:5], 1):
        evidence_text += f"""
SOURCE {i} (Trust: {src['trust_score']:.0%}):
Title: {src['title']}
Domain: {src['domain']}
Snippet: {src['snippet'][:500]}
---"""

    prompt = f"""You are an expert fact-checker performing a RIGOROUS fact verification analysis.

CLAIM TO VERIFY: "{claim}"

RETRIEVED EVIDENCE:
{evidence_text}

INSTRUCTIONS (Chain of Thought):
Step 1 - READ all evidence carefully
Step 2 - IDENTIFY which parts of evidence support or contradict the claim
Step 3 - CHECK if evidence is from high-trust sources (gov, edu, established news)
Step 4 - DETECT any conflicting information between sources
Step 5 - ASSESS temporal accuracy (is the claim still current?)
Step 6 - DETERMINE final verdict based ONLY on provided evidence (NOT your training data)

STRICT CONSTRAINTS:
- Never use prior knowledge, assumptions, or unstated facts.
- If evidence is insufficient, unclear, or does not directly address the claim, return UNVERIFIABLE.
- If supporting and contradicting high-trust evidence both exist, return PARTIALLY_TRUE and set conflicting_evidence=true.
- Keep confidence tied to evidence quality and agreement.
- If majority of HIGH-CREDIBILITY sources support the claim and contradictions are minor/low-trust, prefer TRUE.
- Use PARTIALLY_TRUE when there is slight variation in wording/numbers but core fact is supported.
- Use FALSE only when high-credibility evidence clearly contradicts the claim.

CLASSIFICATION RULES:
- TRUE: Multiple high-trust sources clearly confirm the claim
- FALSE: Evidence clearly contradicts the claim
- PARTIALLY_TRUE: Some aspects confirmed, some not, or claim is overstated
- UNVERIFIABLE: Insufficient or no relevant evidence found
- CONFLICTING: Sources directly contradict each other about this claim

Return ONLY valid JSON (no markdown):
{{
  "status": "TRUE|FALSE|PARTIALLY_TRUE|UNVERIFIABLE|CONFLICTING",
  "confidence": 0.0-1.0,
  "reasoning": "Detailed step-by-step Chain of Thought reasoning explaining HOW you reached this verdict based on the evidence. Be specific about which sources support or contradict the claim.",
  "conflicting_evidence": true or false,
  "supporting_sources": [list of source indices 1-based that support the claim],
  "contradicting_sources": [list of source indices 1-based that contradict the claim],
  "key_finding": "One-sentence summary of the key finding"
}}"""

    response = await call_gemini(prompt)
    result = extract_json_from_text(response)
    
    if not isinstance(result, dict):
        return {
            "status": "UNVERIFIABLE",
            "confidence": 0.2,
            "reasoning": "Verification processing error.",
            "conflicting_evidence": False,
            "key_finding": "Unable to process verification"
        }
    
    # Ensure required fields
    result.setdefault("status", "UNVERIFIABLE")
    result.setdefault("confidence", 0.3)
    result.setdefault("reasoning", "No reasoning provided")
    result.setdefault("conflicting_evidence", False)
    result.setdefault("key_finding", result.get("reasoning", "")[:100])

    supporting = _safe_indices(result.get("supporting_sources", []))
    contradicting = _safe_indices(result.get("contradicting_sources", []))

    has_conflict = bool(supporting and contradicting)
    if has_conflict:
        result["conflicting_evidence"] = True
        if result["status"] in {"TRUE", "FALSE", "CONFLICTING"}:
            result["status"] = "PARTIALLY_TRUE"

    result = _normalize_uncertain_true(result, supporting)

    result = _apply_credibility_upgrade_rules(result, evidence_sources, supporting, contradicting)

    result["confidence"] = _compute_confidence(
        status=result.get("status", "UNVERIFIABLE"),
        evidence_sources=evidence_sources,
        supporting=supporting,
        contradicting=contradicting,
    )
    
    return result
