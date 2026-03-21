from pydantic import BaseModel
from typing import List, Optional, Any
from enum import Enum

class VerificationStatus(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    UNVERIFIABLE = "UNVERIFIABLE"
    CONFLICTING = "CONFLICTING"

class Source(BaseModel):
    url: str
    title: str
    snippet: str
    trust_score: float
    domain: str

class Claim(BaseModel):
    id: str
    text: str
    status: VerificationStatus
    confidence: float
    reasoning: str
    sources: List[Source]
    is_temporal: bool = False
    is_hallucination: bool = False
    conflicting_evidence: bool = False
    search_queries: List[str] = []

class VerificationReport(BaseModel):
    id: str
    user_id: str
    input_text: str
    input_type: str  # "text" or "url"
    source_url: Optional[str] = None
    claims: List[Claim]
    overall_accuracy: float
    total_claims: int
    true_count: int
    false_count: int
    partial_count: int
    unverifiable_count: int
    conflicting_count: int
    hallucination_count: int
    pipeline_steps: List[dict]
    created_at: str
    processing_time: float

class VerificationRequest(BaseModel):
    input_type: str  # "text" or "url"
    content: str  # text or URL
