from pydantic import BaseModel
from typing import List, Optional, Any, Dict
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
    supporting_sources: List[int] = []
    contradicting_sources: List[int] = []
    evidence_mapping: Dict[str, Any] = {}


class AITextDetection(BaseModel):
    probability: float
    label: str
    confidence: float
    indicators: List[str] = []
    method: str = "heuristic-v1"


class AIMediaItem(BaseModel):
    type: str
    url: str
    domain: str
    trust_score: float
    synthetic_probability: float
    flags: List[str] = []


class AIMediaDetection(BaseModel):
    overall_probability: float
    label: str
    analyzed_count: int
    items: List[AIMediaItem] = []
    note: str = ""
    method: str = "heuristic-media-v1"

class VerificationReport(BaseModel):
    id: str
    user_id: str
    input_text: str
    input_type: str  # "text" or "url"
    source_url: Optional[str] = None
    claims: List[Claim]
    overall_accuracy: float
    trust_score: float = 0.0
    total_claims: int
    true_count: int
    false_count: int
    partial_count: int
    unverifiable_count: int
    conflicting_count: int
    hallucination_count: int
    ai_text_detection: AITextDetection
    ai_media_detection: AIMediaDetection
    selected_model: str = "gemini"
    model_used: str = "none"
    pipeline_steps: List[dict]
    created_at: str
    processing_time: float

class VerificationRequest(BaseModel):
    input_type: str  # "text" or "url"
    content: str  # text or URL
    preferred_model: Optional[str] = "gemini"
