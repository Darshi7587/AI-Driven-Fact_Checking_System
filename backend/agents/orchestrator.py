from typing import Dict, List, Any
import uuid
import asyncio
import time
from datetime import datetime, timezone

from agents.claim_extractor import extract_claims
from agents.query_generator import generate_search_queries
from agents.web_search_agent import search_and_collect_evidence
from agents.verification_agent import verify_claim
from agents.hallucination_detector import detect_hallucination, check_temporal_validity
from agents.ai_content_detector import detect_ai_generated_text, detect_ai_generated_media
from services.scraper_service import scrape_url, get_trust_score, extract_domain
from services.gemini_service import (
    set_model_preference,
    reset_model_preference,
    clear_model_runtime_info,
    get_model_runtime_info,
    call_gemini,
    extract_json_from_text,
)
from config import MAX_CLAIM_CONCURRENCY, MAX_CLAIMS
from config import FAST_PIPELINE_MODE, FAST_MAX_CLAIMS, FAST_MEDIA_TIMEOUT_SECONDS


VALID_STATUSES = {"TRUE", "FALSE", "PARTIALLY_TRUE", "UNVERIFIABLE", "CONFLICTING"}


def _is_extraordinary_claim_text(claim_text: str) -> bool:
    lowered = (claim_text or "").lower()
    has_secret = any(k in lowered for k in ["secret government", "classified project", "covert program", "secret project", "hidden project"])
    has_alien = any(k in lowered for k in ["alien", "extraterrestrial", "non-human", "uap", "ufo"])
    has_discovery = any(k in lowered for k in ["discovered", "confirmed", "proved", "retrieved", "found"])
    return has_secret and has_alien and has_discovery


async def _run_gemini_precheck(input_type: str, input_text: str) -> Dict:
    sample = (input_text or "").strip()
    if not sample:
        return {
            "performed": False,
            "status": "UNCERTAIN",
            "confidence": 0.3,
            "summary": "Input is empty, so Gemini could not perform a correctness check.",
        }

    prompt = f"""You are performing a fast first-pass fact-check precheck.
Input type: {input_type}
Content sample:
{sample[:1400]}

Return ONLY JSON:
{{
  "status": "LIKELY_CORRECT|LIKELY_INCORRECT|MIXED|UNCERTAIN",
  "confidence": 0.0,
  "summary": "one short sentence"
}}"""

    try:
        raw = await call_gemini(prompt)
        data = extract_json_from_text(raw)
        if isinstance(data, dict):
            status = str(data.get("status", "UNCERTAIN")).upper()
            if status not in {"LIKELY_CORRECT", "LIKELY_INCORRECT", "MIXED", "UNCERTAIN"}:
                status = "UNCERTAIN"
            confidence = float(data.get("confidence", 0.45) or 0.45)
            summary = str(data.get("summary", "Gemini precheck completed.")).strip() or "Gemini precheck completed."
            return {
                "performed": True,
                "status": status,
                "confidence": round(max(0.2, min(confidence, 0.95)), 3),
                "summary": summary,
            }
    except Exception:
        pass

    return {
        "performed": False,
        "status": "UNCERTAIN",
        "confidence": 0.35,
        "summary": "Gemini precheck was unavailable, so only evidence-based scoring is shown.",
    }


def _build_gemini_precheck(
    counts: Dict,
    total: int,
    avg_confidence: float,
    model_used: str,
    selected_model: str,
    precheck_seed: Dict | None = None,
) -> Dict:
    true_count = int(counts.get("TRUE", 0))
    false_count = int(counts.get("FALSE", 0))
    partial_count = int(counts.get("PARTIALLY_TRUE", 0))
    unverifiable_count = int(counts.get("UNVERIFIABLE", 0))

    support_score = true_count + (0.5 * partial_count)
    oppose_score = float(false_count)
    coverage = ((true_count + false_count + partial_count) / max(total, 1)) if total > 0 else 0.0

    if total == 0:
        status = "UNCERTAIN"
        summary = "No claims were extracted, so Gemini could not determine correctness."
    elif support_score >= max(1.0, oppose_score * 1.5) and unverifiable_count <= int(total * 0.4):
        status = "LIKELY_CORRECT"
        summary = "Gemini check indicates the input is mostly correct based on currently verified claims."
    elif oppose_score > support_score and false_count >= 1:
        status = "LIKELY_INCORRECT"
        summary = "Gemini check indicates notable incorrect content in the input."
    elif (true_count + false_count + partial_count) > 0:
        status = "MIXED"
        summary = "Gemini check indicates mixed correctness; some claims are supported while others are weak or unverified."
    else:
        status = "UNCERTAIN"
        summary = "Gemini check is inconclusive due to limited direct evidence."

    confidence = min(0.95, max(0.30, (avg_confidence * 0.65) + (coverage * 0.35)))

    if isinstance(precheck_seed, dict) and precheck_seed:
        seeded_status = str(precheck_seed.get("status", "")).upper().strip()
        if seeded_status in {"LIKELY_CORRECT", "LIKELY_INCORRECT", "MIXED", "UNCERTAIN"}:
            status = seeded_status
        seeded_summary = str(precheck_seed.get("summary", "")).strip()
        if seeded_summary:
            summary = seeded_summary
        seeded_conf = float(precheck_seed.get("confidence", confidence) or confidence)
        confidence = (confidence * 0.5) + (max(0.2, min(seeded_conf, 0.95)) * 0.5)

    return {
        "performed": bool((precheck_seed or {}).get("performed", False)) or selected_model == "gemini" or model_used == "gemini",
        "status": status,
        "confidence": round(confidence, 3),
        "summary": summary,
        "evidence": {
            "true": true_count,
            "partial": partial_count,
            "false": false_count,
            "unverifiable": unverifiable_count,
        },
    }


def _build_claim_evidence_digest(claim: Dict) -> List[Dict[str, Any]]:
    digest = []
    for src in (claim.get("sources", []) or [])[:3]:
        digest.append(
            {
                "domain": src.get("domain", ""),
                "trust_score": float(src.get("trust_score", 0.5) or 0.5),
                "title": (src.get("title", "") or "")[:180],
                "snippet": (src.get("snippet", "") or "")[:280],
            }
        )
    return digest


def _compute_aggregate_metrics(processed_claims: List[Dict], hallucination_count: int) -> Dict[str, Any]:
    counts = {"TRUE": 0, "FALSE": 0, "PARTIALLY_TRUE": 0, "UNVERIFIABLE": 0, "CONFLICTING": 0}
    for claim in processed_claims:
        status = claim.get("status", "UNVERIFIABLE")
        if status not in counts:
            status = "UNVERIFIABLE"
        counts[status] += 1

    total = len(processed_claims)
    true_weight = counts.get("TRUE", 0) * 1.0
    partial_weight = counts.get("PARTIALLY_TRUE", 0) * 0.5
    overall_accuracy = (true_weight + partial_weight) / total if total > 0 else 0.0

    weighted_balance = 0.0
    confidence_sum = 0.0
    for claim in processed_claims:
        conf = float(claim.get("confidence", 0.0) or 0.0)
        conf = max(0.0, min(conf, 1.0))
        confidence_sum += conf
        status = claim.get("status", "UNVERIFIABLE")
        if status == "TRUE":
            weighted_balance += conf
        elif status == "PARTIALLY_TRUE":
            weighted_balance += 0.5 * conf
        elif status == "FALSE":
            weighted_balance -= conf
        elif status == "CONFLICTING":
            weighted_balance += 0.1 * conf

    trust_score = 0.5 + (weighted_balance / (2 * max(total, 1)))
    trust_score = max(0.0, min(trust_score, 1.0))
    avg_confidence = (confidence_sum / total) if total > 0 else 0.0

    return {
        "counts": counts,
        "total": total,
        "overall_accuracy": round(overall_accuracy, 3),
        "trust_score": round(trust_score, 3),
        "avg_confidence": round(avg_confidence, 3),
        "hallucination_count": hallucination_count,
    }


async def _run_gemini_claim_adjudication(input_type: str, input_text: str, claims: List[Dict]) -> Dict[str, Any]:
    payload_claims = []
    for idx, claim in enumerate(claims, 1):
        payload_claims.append(
            {
                "index": idx,
                "claim_text": claim.get("text", ""),
                "pipeline_status": claim.get("status", "UNVERIFIABLE"),
                "pipeline_confidence": float(claim.get("confidence", 0.3) or 0.3),
                "evidence": _build_claim_evidence_digest(claim),
            }
        )

    prompt = f"""You are a fact-check chatbot adjudicator.
Your job:
1) Independently judge each claim using ONLY the provided evidence snippets.
2) Compare your judgment with pipeline_status.
3) If pipeline_status is wrong, set replace_pipeline=true and provide corrected status.

Allowed statuses: TRUE, FALSE, PARTIALLY_TRUE, UNVERIFIABLE, CONFLICTING.
Be strict: if evidence is weak or purely indirect, use UNVERIFIABLE or PARTIALLY_TRUE.

INPUT_TYPE: {input_type}
CONTENT_SAMPLE:
{(input_text or '')[:1200]}

CLAIMS_AND_EVIDENCE_JSON:
{payload_claims}

Return ONLY JSON:
{{
  "overall_summary": "short chatbot-style summary",
  "adjudications": [
    {{
      "index": 1,
      "status": "TRUE|FALSE|PARTIALLY_TRUE|UNVERIFIABLE|CONFLICTING",
      "confidence": 0.0,
      "reasoning": "1-2 sentences",
      "key_finding": "one short finding",
      "replace_pipeline": true
    }}
  ]
}}"""

    try:
        raw = await call_gemini(prompt)
        data = extract_json_from_text(raw)
        if not isinstance(data, dict):
            raise ValueError("Gemini adjudication parse failure")

        adjudications = data.get("adjudications", [])
        if not isinstance(adjudications, list):
            adjudications = []

        cleaned = []
        for item in adjudications:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("index"))
            except Exception:
                continue
            status = str(item.get("status", "UNVERIFIABLE")).upper().strip()
            if status not in VALID_STATUSES:
                status = "UNVERIFIABLE"
            confidence = float(item.get("confidence", 0.45) or 0.45)
            cleaned.append(
                {
                    "index": idx,
                    "status": status,
                    "confidence": round(max(0.15, min(confidence, 0.98)), 3),
                    "reasoning": str(item.get("reasoning", "Gemini adjudication applied.")).strip(),
                    "key_finding": str(item.get("key_finding", "Gemini provided a corrected claim assessment.")).strip(),
                    "replace_pipeline": bool(item.get("replace_pipeline", False)),
                }
            )

        return {
            "performed": True,
            "overall_summary": str(data.get("overall_summary", "Gemini adjudication completed.")).strip() or "Gemini adjudication completed.",
            "adjudications": cleaned,
        }
    except Exception as exc:
        return {
            "performed": False,
            "overall_summary": f"Gemini adjudication unavailable: {exc}",
            "adjudications": [],
        }


async def run_verification_pipeline(
    input_type: str,
    content: str,
    preferred_model: str = "gemini",
    on_progress=None,
) -> Dict:
    """Master orchestrator that runs the full multi-agent verification pipeline."""
    start_time = time.time()
    pipeline_steps = []
    preference_token = set_model_preference(preferred_model)
    clear_model_runtime_info()

    def add_step(step_name: str, status: str, detail: str = ""):
        pipeline_steps.append(
            {
                "step": step_name,
                "status": status,
                "detail": detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    try:
        add_step("Preprocessing", "completed", f"Input type: {input_type}")
        add_step("Model Selection", "completed", f"Preferred model: {(preferred_model or 'auto').lower()}")

        input_text = content
        source_url = None
        gemini_precheck_seed = {
            "performed": False,
            "status": "UNCERTAIN",
            "confidence": 0.35,
            "summary": "Gemini precheck was not executed.",
        }

        if input_type == "url":
            source_url = content
            add_step("URL Scraping", "running", f"Fetching {content}")
            scraped = await scrape_url(content)
            if not scraped:
                add_step("URL Scraping", "failed", "Could not scrape URL content, using URL text fallback")
                input_text = content
            else:
                input_text = scraped
                add_step("URL Scraping", "completed", f"Scraped {len(scraped)} characters")

        add_step("Gemini Correctness Check", "running", "Running fast Gemini correctness precheck")
        gemini_precheck_seed = await _run_gemini_precheck(input_type=input_type, input_text=input_text)
        add_step("Gemini Correctness Check", "completed", f"Status: {gemini_precheck_seed.get('status', 'UNCERTAIN')}")

        add_step("AI Text Detection", "running", "Estimating human-vs-LLM authorship probability")
        ai_text_detection = detect_ai_generated_text(input_text)
        add_step(
            "AI Text Detection",
            "completed",
            f"AI probability: {round(ai_text_detection.get('probability', 0) * 100)}%",
        )

        media_task = None
        if input_type == "url":
            add_step("AI Media Detection", "running", "Analyzing embedded media authenticity")
            media_task = asyncio.create_task(
                detect_ai_generated_media(input_type=input_type, content=content, source_url=source_url)
            )

        add_step("Claim Extraction", "running", "Using selected model to extract atomic facts")
        raw_claims = await extract_claims(input_text)

        if not raw_claims:
            fallback_text = input_text.strip()[:220] or "Input content could not be processed into explicit claims."
            raw_claims = [
                {
                    "claim_text": fallback_text,
                    "is_temporal": False,
                    "category": "other",
                }
            ]
            add_step("Claim Extraction", "completed", "Used fallback claim extraction")
        else:
            add_step("Claim Extraction", "completed", f"Extracted {len(raw_claims)} verifiable claims")

        claims_cap = FAST_MAX_CLAIMS if FAST_PIPELINE_MODE else MAX_CLAIMS
        raw_claims = raw_claims[: max(1, claims_cap)]
        add_step("Claim Selection", "completed", f"Processing top {len(raw_claims)} claims")

        claim_concurrency = (MAX_CLAIM_CONCURRENCY + 1) if FAST_PIPELINE_MODE else MAX_CLAIM_CONCURRENCY
        claim_semaphore = asyncio.Semaphore(max(1, claim_concurrency))

        async def process_claim(i: int, raw_claim: Dict):
            async with claim_semaphore:
                claim_text = raw_claim.get("claim_text", "")
                is_temporal = raw_claim.get("is_temporal", False)
                claim_id = str(uuid.uuid4())

                try:
                    add_step(
                        f"Query Generation [{i+1}/{len(raw_claims)}]",
                        "running",
                        f"Generating queries for: {claim_text[:60]}...",
                    )
                    queries = await generate_search_queries(claim_text)
                    if not queries:
                        queries = [f"{claim_text} latest data official source"]
                    add_step(
                        f"Query Generation [{i+1}/{len(raw_claims)}]",
                        "completed",
                        f"Generated {len(queries)} queries",
                    )
                except Exception:
                    queries = [f"{claim_text} latest data official source"]
                    add_step(f"Query Generation [{i+1}/{len(raw_claims)}]", "failed", "Using fallback query")

                try:
                    add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "running", f"Searching {len(queries)} queries")
                    evidence = await search_and_collect_evidence(claim_text, queries)

                    # Fallback anchor: include original URL as evidence for URL inputs.
                    if source_url:
                        source_snippet = (input_text or "")[:900]
                        source_evidence = {
                            "url": source_url,
                            "title": "Source article (input URL)",
                            "snippet": source_snippet,
                            "trust_score": get_trust_score(source_url),
                            "domain": extract_domain(source_url),
                            "image_url": None,
                        }
                        existing_urls = {e.get("url", "") for e in evidence}
                        if source_url not in existing_urls:
                            evidence.insert(0, source_evidence)

                    add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "completed", f"Found {len(evidence)} sources")
                except Exception:
                    evidence = []
                    add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "failed", "Evidence search failed")

                try:
                    add_step(f"Verification [{i+1}/{len(raw_claims)}]", "running", "Analyzing evidence")
                    verification = await verify_claim(claim_text, evidence)
                    add_step(
                        f"Verification [{i+1}/{len(raw_claims)}]",
                        "completed",
                        f"Result: {verification.get('status', 'UNKNOWN')}",
                    )
                except Exception:
                    verification = {
                        "status": "UNVERIFIABLE",
                        "confidence": 0.2,
                        "reasoning": "Verification model unavailable for this claim; fallback applied.",
                        "key_finding": "Could not complete model-based verification for this claim.",
                        "conflicting_evidence": False,
                    }
                    add_step(
                        f"Verification [{i+1}/{len(raw_claims)}]",
                        "failed",
                        "Verification failed; fallback verdict used",
                    )

                try:
                    hallucination_info = await detect_hallucination(claim_text, verification, evidence)
                except Exception:
                    hallucination_info = {"is_hallucination": False, "hallucination_score": 0}

                try:
                    if FAST_PIPELINE_MODE:
                        temporal_info = {
                            "temporal_note": "Fast mode: temporal validation used rule-based heuristics.",
                        }
                    else:
                        temporal_info = await check_temporal_validity(claim_text, is_temporal)
                except Exception:
                    temporal_info = {"temporal_note": ""}

                status = verification.get("status", "UNVERIFIABLE")
                processed = {
                    "id": claim_id,
                    "text": claim_text,
                    "status": status,
                    "confidence": verification.get("confidence", 0.5),
                    "reasoning": verification.get("reasoning", ""),
                    "key_finding": verification.get("key_finding", ""),
                    "sources": evidence,
                    "supporting_sources": verification.get("supporting_sources", []),
                    "contradicting_sources": verification.get("contradicting_sources", []),
                    "decision_flags": verification.get("decision_flags", []),
                    "evidence_mapping": verification.get("evidence_mapping", {"supporting": [], "contradicting": []}),
                    "is_temporal": is_temporal,
                    "temporal_note": temporal_info.get("temporal_note", ""),
                    "is_hallucination": hallucination_info.get("is_hallucination", False),
                    "hallucination_score": hallucination_info.get("hallucination_score", 0),
                    "conflicting_evidence": verification.get("conflicting_evidence", False),
                    "search_queries": queries,
                    "category": raw_claim.get("category", "other"),
                }

                return {
                    "index": i,
                    "status": status,
                    "is_hallucination": bool(hallucination_info.get("is_hallucination")),
                    "processed": processed,
                }

        claim_results = await asyncio.gather(
            *(process_claim(i, raw_claim) for i, raw_claim in enumerate(raw_claims)),
            return_exceptions=True,
        )

        processed_claims = []
        counts = {"TRUE": 0, "FALSE": 0, "PARTIALLY_TRUE": 0, "UNVERIFIABLE": 0, "CONFLICTING": 0}
        hallucination_count = 0

        for i, result in enumerate(claim_results):
            if isinstance(result, Exception):
                claim_text = raw_claims[i].get("claim_text", "")
                processed = {
                    "id": str(uuid.uuid4()),
                    "text": claim_text,
                    "status": "UNVERIFIABLE",
                    "confidence": 0.2,
                    "reasoning": "Verification step failed for this claim.",
                    "key_finding": "Unable to verify due to processing error.",
                    "sources": [],
                    "supporting_sources": [],
                    "contradicting_sources": [],
                    "decision_flags": ["Weak Evidence", "Emerging Claim"],
                    "evidence_mapping": {"supporting": [], "contradicting": []},
                    "is_temporal": bool(raw_claims[i].get("is_temporal", False)),
                    "temporal_note": "",
                    "is_hallucination": False,
                    "hallucination_score": 0,
                    "conflicting_evidence": False,
                    "search_queries": [],
                    "category": raw_claims[i].get("category", "other"),
                }
                processed_claims.append((i, processed))
                counts["UNVERIFIABLE"] += 1
                continue

            counts[result["status"]] = counts.get(result["status"], 0) + 1
            if result["is_hallucination"]:
                hallucination_count += 1
            processed_claims.append((result["index"], result["processed"]))

        processed_claims.sort(key=lambda item: item[0])
        processed_claims = [item[1] for item in processed_claims]

        add_step("Gemini Adjudication", "running", "Comparing pipeline verdicts with Gemini chatbot verdicts")
        gemini_adjudication = await _run_gemini_claim_adjudication(
            input_type=input_type,
            input_text=input_text,
            claims=processed_claims,
        )

        replacements = 0
        for adj in gemini_adjudication.get("adjudications", []):
            idx = int(adj.get("index", 0)) - 1
            if idx < 0 or idx >= len(processed_claims):
                continue
            claim_obj = processed_claims[idx]
            pipeline_status = claim_obj.get("status", "UNVERIFIABLE")
            adjudicated_status = adj.get("status", pipeline_status)

            # Guardrail: for extraordinary conspiracy-style claims, do not let chatbot adjudication
            # soften strict evidence policy unless it provides clear contradiction/confirmation via pipeline.
            if _is_extraordinary_claim_text(claim_obj.get("text", "")):
                if pipeline_status in {"FALSE", "UNVERIFIABLE"} and adjudicated_status in {"PARTIALLY_TRUE", "TRUE"}:
                    continue

            should_replace = bool(adj.get("replace_pipeline", False)) or (pipeline_status != adj.get("status"))
            if not should_replace:
                continue

            replacements += 1
            claim_obj["status"] = adjudicated_status
            claim_obj["confidence"] = float(adj.get("confidence", claim_obj.get("confidence", 0.4)) or claim_obj.get("confidence", 0.4))
            claim_obj["reasoning"] = adj.get("reasoning", claim_obj.get("reasoning", ""))
            claim_obj["key_finding"] = adj.get("key_finding", claim_obj.get("key_finding", ""))
            claim_obj["gemini_override"] = True

        gemini_adjudication["replacements_applied"] = replacements
        add_step("Gemini Adjudication", "completed", f"Applied {replacements} Gemini override(s)")

        aggregate = _compute_aggregate_metrics(processed_claims, hallucination_count)
        counts = aggregate["counts"]
        total = aggregate["total"]
        overall_accuracy = aggregate["overall_accuracy"]
        trust_score = aggregate["trust_score"]
        avg_confidence = aggregate["avg_confidence"]

        processing_time = time.time() - start_time
        add_step("Report Generation", "completed", f"Total time: {processing_time:.1f}s")
        verified_as_of = datetime.now(timezone.utc).strftime("%B %Y")

        if media_task:
            try:
                if FAST_PIPELINE_MODE:
                    ai_media_detection = await asyncio.wait_for(media_task, timeout=max(2.0, FAST_MEDIA_TIMEOUT_SECONDS))
                else:
                    ai_media_detection = await media_task
                add_step(
                    "AI Media Detection",
                    "completed",
                    f"Media analyzed: {ai_media_detection.get('analyzed_count', 0)}",
                )
            except Exception:
                ai_media_detection = {
                    "overall_probability": 0.0,
                    "label": "unknown",
                    "analyzed_count": 0,
                    "items": [],
                    "note": "Media analysis failed or timed out in fast mode.",
                    "content_bytes_analyzed": False,
                    "confidence_calibration_note": "Timed out before media calibration completed.",
                    "method": "hybrid-media-v2",
                }
                add_step("AI Media Detection", "failed", "Media analysis failed")
        else:
            ai_media_detection = {
                "overall_probability": 0.0,
                "label": "not_applicable",
                "analyzed_count": 0,
                "items": [],
                "note": "Media analysis runs for URL inputs.",
                "content_bytes_analyzed": False,
                "confidence_calibration_note": "Not applicable for text-only input without media URLs.",
                "method": "hybrid-media-v2",
            }

        model_info = get_model_runtime_info()
        gemini_precheck = _build_gemini_precheck(
            counts=counts,
            total=total,
            avg_confidence=avg_confidence,
            model_used=model_info["model_used"],
            selected_model=model_info["selected_model"],
            precheck_seed=gemini_precheck_seed,
        )
        add_step(
            "Model Usage",
            "completed",
            f"Selected: {model_info['selected_model']}, Used: {model_info['model_used']}",
        )

        return {
            "input_text": input_text[:5000],
            "input_type": input_type,
            "source_url": source_url,
            "claims": processed_claims,
            "gemini_precheck": gemini_precheck,
            "gemini_adjudication": gemini_adjudication,
            "overall_accuracy": overall_accuracy,
            "trust_score": trust_score,
            "avg_confidence": avg_confidence,
            "total_claims": total,
            "true_count": counts.get("TRUE", 0),
            "false_count": counts.get("FALSE", 0),
            "partial_count": counts.get("PARTIALLY_TRUE", 0),
            "unverifiable_count": counts.get("UNVERIFIABLE", 0),
            "conflicting_count": counts.get("CONFLICTING", 0),
            "hallucination_count": hallucination_count,
            "ai_text_detection": ai_text_detection,
            "ai_media_detection": ai_media_detection,
            "selected_model": model_info["selected_model"],
            "model_used": model_info["model_used"],
            "verified_as_of": verified_as_of,
            "pipeline_steps": pipeline_steps,
            "processing_time": round(processing_time, 2),
        }
    finally:
        reset_model_preference(preference_token)
