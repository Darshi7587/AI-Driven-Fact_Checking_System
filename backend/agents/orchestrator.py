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
from services.scraper_service import scrape_url

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
            add_step("URL Scraping", "failed", "Could not scrape URL content")
            raise ValueError("Failed to scrape content from URL")
        input_text = scraped
        add_step("URL Scraping", "completed", f"Scraped {len(scraped)} characters")
    
    # Step 2: Claim Extraction
    add_step("Claim Extraction", "running", "Using Gemini to extract atomic facts")
    raw_claims = await extract_claims(input_text)
    
    if not raw_claims:
        raise ValueError("No verifiable claims could be extracted from the input")
    
    add_step("Claim Extraction", "completed", f"Extracted {len(raw_claims)} verifiable claims")
    
    # Step 3-7: Process each claim through the pipeline
    processed_claims = []
    counts = {"TRUE": 0, "FALSE": 0, "PARTIALLY_TRUE": 0, "UNVERIFIABLE": 0, "CONFLICTING": 0}
    hallucination_count = 0
    
    for i, raw_claim in enumerate(raw_claims):
        claim_text = raw_claim.get("claim_text", "")
        is_temporal = raw_claim.get("is_temporal", False)
        claim_id = str(uuid.uuid4())
        
        add_step(f"Query Generation [{i+1}/{len(raw_claims)}]", "running", f"Generating queries for: {claim_text[:60]}...")
        
        # Generate search queries
        queries = await generate_search_queries(claim_text)
        add_step(f"Query Generation [{i+1}/{len(raw_claims)}]", "completed", f"Generated {len(queries)} queries")
        
        # Search for evidence
        add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "running", f"Searching {len(queries)} queries")
        evidence = await search_and_collect_evidence(claim_text, queries)
        add_step(f"Web Search [{i+1}/{len(raw_claims)}]", "completed", f"Found {len(evidence)} sources")
        
        # Verify claim
        add_step(f"Verification [{i+1}/{len(raw_claims)}]", "running", "Analyzing evidence with Gemini")
        verification = await verify_claim(claim_text, evidence)
        add_step(f"Verification [{i+1}/{len(raw_claims)}]", "completed", 
                 f"Result: {verification.get('status', 'UNKNOWN')}")
        
        # Hallucination detection
        hallucination_info = await detect_hallucination(claim_text, verification, evidence)
        temporal_info = await check_temporal_validity(claim_text, is_temporal)
        
        status = verification.get("status", "UNVERIFIABLE")
        counts[status] = counts.get(status, 0) + 1
        
        if hallucination_info.get("is_hallucination"):
            hallucination_count += 1
        
        processed_claims.append({
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
        })
        
        await asyncio.sleep(0.3)  # Small delay between claims
    
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
        "pipeline_steps": pipeline_steps,
        "processing_time": round(processing_time, 2)
    }
