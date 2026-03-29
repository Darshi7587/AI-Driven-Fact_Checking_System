from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.report_model import VerificationRequest
from agents.orchestrator import run_verification_pipeline
from agents.ai_content_detector import detect_ai_generated_text, detect_ai_generated_uploaded_media
from auth.jwt_handler import decode_access_token
from services.gemini_service import GeminiServiceError, detect_ai_text_with_gemini, detect_ai_media_with_gemini
import uuid
from datetime import datetime, timezone
from typing import Optional

router = APIRouter()
security = HTTPBearer()


def _attach_media_verdict(media_result: dict) -> dict:
    if not isinstance(media_result, dict):
        return media_result

    prob = media_result.get("overall_probability", 0.0)
    try:
        deepfake_probability = max(0.0, min(1.0, float(prob)))
    except (TypeError, ValueError):
        deepfake_probability = 0.0

    verdict = "deepfake" if deepfake_probability >= 0.5 else "real"
    media_result["verdict"] = verdict
    media_result["deepfake_probability"] = round(deepfake_probability, 3)
    media_result["real_probability"] = round(1.0 - deepfake_probability, 3)
    media_result["borderline"] = 0.4 <= deepfake_probability <= 0.6

    # Normalize confidence to 0..100 for UI readability.
    confidence = media_result.get("confidence")
    try:
        c = float(confidence)
        if c <= 1.0:
            c *= 100.0
    except (TypeError, ValueError):
        c = abs(deepfake_probability - 0.5) * 200.0
    media_result["confidence"] = round(max(0.0, min(100.0, c)), 1)

    # Keep ai_probability in 0..100 while preserving overall_probability in 0..1.
    ai_prob = media_result.get("ai_probability")
    try:
        ap = float(ai_prob)
        if ap <= 1.0:
            ap *= 100.0
    except (TypeError, ValueError):
        ap = deepfake_probability * 100.0
    media_result["ai_probability"] = round(max(0.0, min(100.0, ap)), 1)

    return media_result

def get_db(request: Request):
    return request.app.state.db

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload.get("user_id", "anonymous")

@router.post("/")
async def verify_content(
    request: Request,
    body: VerificationRequest,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db(request)
    
    if not body.content or len(body.content.strip()) < 20:
        raise HTTPException(status_code=400, detail="Content too short to verify")
    
    if body.input_type not in ["text", "url"]:
        raise HTTPException(status_code=400, detail="input_type must be 'text' or 'url'")
    
    try:
        result = await run_verification_pipeline(
            input_type=body.input_type,
            content=body.content.strip(),
            preferred_model="gemini"
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except GeminiServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    
    # Save to database
    report_id = str(uuid.uuid4())
    report_doc = {
        "_id": report_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **result
    }
    
    try:
        await db.reports.insert_one(report_doc)
        await db.users.update_one(
            {"_id": user_id},
            {"$inc": {"total_checks": 1}}
        )
    except Exception:
        pass  # Don't fail if DB save fails
    
    return {
        "id": report_id,
        "user_id": user_id,
        "created_at": report_doc["created_at"],
        **result
    }

@router.get("/{report_id}")
async def get_report(
    report_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db(request)
    report = await db.reports.find_one({"_id": report_id, "user_id": user_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report["id"] = report.pop("_id")
    return report


@router.post("/ai-detect")
async def detect_ai_content(
    text: Optional[str] = Form(default=None),
    media_file: Optional[UploadFile] = File(default=None),
    user_id: str = Depends(get_current_user_id),
):
    if (not text or not text.strip()) and media_file is None:
        raise HTTPException(status_code=400, detail="Provide text or upload a media file.")

    response = {
        "user_id": user_id,
        "text_detection": None,
        "media_detection": None,
    }

    if text and text.strip():
        if len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="Text must be at least 10 characters.")
        clean_text = text.strip()
        try:
            response["text_detection"] = await detect_ai_text_with_gemini(clean_text)
        except GeminiServiceError as e:
            fallback = detect_ai_generated_text(clean_text)
            fallback["fallback_reason"] = str(e)
            response["text_detection"] = fallback

    if media_file is not None:
        raw = await media_file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Keep uploads bounded to avoid memory pressure on API workers.
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Uploaded file is too large (max 8MB).")

        file_name = media_file.filename or "upload"
        content_type = media_file.content_type or ""
        is_image = (content_type or "").lower().startswith("image/")

        try:
            response["media_detection"] = await detect_ai_media_with_gemini(
                file_name=file_name,
                content_type=content_type,
                file_bytes=raw,
            )
        except GeminiServiceError as e:
            if is_image:
                # Hugging Face-first image path: if primary detector fails, do not emit an aggressive synthetic verdict.
                response["media_detection"] = {
                    "prediction": "Possibly AI",
                    "ai_probability": 50.0,
                    "confidence": 20.0,
                    "huggingface_score": 50.0,
                    "visual_evidence": [
                        "Primary Hugging Face image detector was unavailable for this request.",
                        "A conservative fallback response was returned to avoid false positives.",
                    ],
                    "final_explanation": "Unable to complete Hugging Face-first image verification. Please retry once Hugging Face service is available.",
                    "overall_probability": 0.5,
                    "label": "uncertain",
                    "analyzed_count": 0,
                    "items": [],
                    "content_bytes_analyzed": False,
                    "confidence_calibration_note": "Confidence is intentionally reduced because the primary Hugging Face signal was unavailable.",
                    "method": "hf-unavailable-safe-fallback-v1",
                    "fallback_reason": str(e),
                }
            else:
                fallback = detect_ai_generated_uploaded_media(
                    file_name=file_name,
                    content_type=content_type,
                    file_bytes=raw,
                )
                fallback["fallback_reason"] = str(e)
                response["media_detection"] = fallback

        response["media_detection"] = _attach_media_verdict(response["media_detection"])

    return response
