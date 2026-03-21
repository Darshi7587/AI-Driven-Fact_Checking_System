from services.gemini_service import call_gemini, extract_json_from_text
from typing import List, Dict
import json

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
Step 6 - DETERMINE final verdict based ONLY on evidence (NOT your training data)

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
    
    return result
