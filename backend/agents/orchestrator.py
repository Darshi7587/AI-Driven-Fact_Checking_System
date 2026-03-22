from typing import List, Dict
import uuid
import asyncio
import time
from datetime import datetime, timezone

from agents.claim_extractor import extract_claims, extract_claims_from_url
from agents.query_generator import generate_search_queries
from agents.web_search_agent import search_and_collect_evidence
from agents.verification_agent import verify_claim
from agents.hallucination_detector import detect_hallucination, check_temporal_validity
from agents.ai_content_detector import detect_ai_generated_text, detect_ai_generated_media
from services.scraper_service import scrape_url
from config import MAX_CLAIM_CONCURRENCY, MAX_CLAIMS

async def run_verification_pipeline(
    input_type: str,
    content: str,
    on_progress=None
) -> Dict:
    """
    Master orchestrator that runs the full multi-agent verification pipeline.
    """
    start_time = time.time()
    pipeline_steps = []
    
    def add_step(step_name: str, status: str, detail: str = ""):
        pipeline_steps.append({
            "step": step_name,
            "status": status,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    # Step 1: Content Preprocessing
    add_step("Preprocessing", "completed", f"Input type: {input_type}")
    input_text = content
    source_url = None
    
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

    # Bonus: AI-generated text detection score
    add_step("AI Text Detection", "running", "Estimating human-vs-LLM authorship probability")
    ai_text_detection = detect_ai_generated_text(input_text)
    add_step(
        "AI Text Detection",
        "completed",
        f"AI probability: {round(ai_text_detection.get('probability', 0) * 100)}%",
    )

    # Bonus: AI-generated media detection for URL inputs (run in parallel where applicable).
    media_task = None
    if input_type == "url":
        add_step("AI Media Detection", "running", "Analyzing embedded media authenticity")
        media_task = asyncio.create_task(
            detect_ai_generated_media(input_type=input_type, content=content, source_url=source_url)
        )
    
    # Step 2: Claim Extraction
    add_step("Claim Extraction", "running", "Using Gemini to extract atomic facts")
    raw_claims = await extract_claims(input_text)
    
    if not raw_claims:
        fallback_text = input_text.strip()[:220]
        if not fallback_text:
            fallback_text = "Input content could not be processed into explicit claims."
        raw_claims = [{
            "claim_text": fallback_text,
            "is_temporal": False,
            "category": "other",
        }]
        add_step("Claim Extraction", "completed", "Used fallback claim extraction")
    else:
        add_step("Claim Extraction", "completed", f"Extracted {len(raw_claims)} verifiable claims")

    raw_claims = raw_claims[:max(1, MAX_CLAIMS)]
    add_step("Claim Selection", "completed", f"Processing top {len(raw_claims)} claims")
    
    # Step 3-7: Process each claim through the pipeline (concurrently with bounded parallelism)
    claim_semaphore = asyncio.Semaphore(max(1, MAX_CLAIM_CONCURRENCY))

    async def process_claim(i: int, raw_claim: Dict):
        async with claim_semaphore:
            claim_text = raw_claim.get("claim_text", "")
            is_temporal = raw_claim.get("is_temporal", False)
            claim_id = str(uuid.uuid4())

            try:
                add_step(f"Query Generation [{i+1}/{len(raw_claims)}]", "running", f"Generating queries for: {claim_text[:60]}...")
                queries = await generate_search_queries(claim_text)
                if not queries:
                    queries = [f"{claim_text} latest data official source"]
                add_step(f"Query Generation [{i+1}/{len(raw_claims)}]", "completed", f"Generated {len(queries)} queries")
            except Exception:
                queries = [f"{claim_text} latest data official source"]
                add_step(f"Query Generation [{i+1}/{len(raw_claims)}]", "failed", "Using fallback query")

            try:
                add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "running", f"Searching {len(queries)} queries")
                evidence = await search_and_collect_evidence(claim_text, queries)
                add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "completed", f"Found {len(evidence)} sources")
            except Exception:
                evidence = []
                add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "failed", "Evidence search failed")

            try:
                add_step(f"Verification [{i+1}/{len(raw_claims)}]", "running", "Analyzing evidence with Gemini")
                verification = await verify_claim(claim_text, evidence)
                add_step(f"Verification [{i+1}/{len(raw_claims)}]", "completed", f"Result: {verification.get('status', 'UNKNOWN')}")
            except Exception:
                verification = {
                    "status": "UNVERIFIABLE",
                    "confidence": 0.2,
                    "reasoning": "Verification model unavailable for this claim; fallback applied.",
                    "key_finding": "Could not complete model-based verification for this claim.",
                    "conflicting_evidence": False,
                }
                add_step(f"Verification [{i+1}/{len(raw_claims)}]", "failed", "Verification failed; fallback verdict used")

            try:
                hallucination_info = await detect_hallucination(claim_text, verification, evidence)
            except Exception:
                hallucination_info = {"is_hallucination": False, "hallucination_score": 0}

            try:
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
                "is_temporal": is_temporal,
                "temporal_note": temporal_info.get("temporal_note", ""),
                "is_hallucination": hallucination_info.get("is_hallucination", False),
                "hallucination_score": hallucination_info.get("hallucination_score", 0),
                "conflicting_evidence": verification.get("conflicting_evidence", False),
                "search_queries": queries,
                "category": raw_claim.get("category", "other")
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
                "is_temporal": bool(raw_claims[i].get("is_temporal", False)),
                "temporal_note": "",
                "is_hallucination": False,
                "hallucination_score": 0,
                "conflicting_evidence": False,
                "search_queries": [],
                "category": raw_claims[i].get("category", "other")
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
    
    # Calculate overall accuracy score
    total = len(processed_claims)
    true_weight = counts.get("TRUE", 0) * 1.0
    partial_weight = counts.get("PARTIALLY_TRUE", 0) * 0.5
    false_weight = counts.get("FALSE", 0) * 0.0
    unverifiable = counts.get("UNVERIFIABLE", 0)
    verifiable_total = total - unverifiable
    
    if verifiable_total > 0:
        overall_accuracy = (true_weight + partial_weight) / verifiable_total
    else:
        overall_accuracy = 0.5
    
    processing_time = time.time() - start_time
    add_step("Report Generation", "completed", f"Total time: {processing_time:.1f}s")
    verified_as_of = datetime.now(timezone.utc).strftime("%B %Y")

    if media_task:
        try:
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
                "note": "Media analysis failed.",
                "method": "heuristic-media-v1",
            }
            add_step("AI Media Detection", "failed", "Media analysis failed")
    else:
        ai_media_detection = {
            "overall_probability": 0.0,
            "label": "not_applicable",
            "analyzed_count": 0,
            "items": [],
            "note": "Media analysis runs for URL inputs.",
            "method": "heuristic-media-v1",
        }
    
    return {
        "input_text": input_text[:5000],
        "input_type": input_type,
        "source_url": source_url,
        "claims": processed_claims,
        "overall_accuracy": round(overall_accuracy, 3),
        "total_claims": total,
        "true_count": counts.get("TRUE", 0),
        "false_count": counts.get("FALSE", 0),
        "partial_count": counts.get("PARTIALLY_TRUE", 0),
        "unverifiable_count": counts.get("UNVERIFIABLE", 0),
        "conflicting_count": counts.get("CONFLICTING", 0),
        "hallucination_count": hallucination_count,
        "ai_text_detection": ai_text_detection,
        "ai_media_detection": ai_media_detection,
        "verified_as_of": verified_as_of,
        "pipeline_steps": pipeline_steps,
        "processing_time": round(processing_time, 2)
    }
