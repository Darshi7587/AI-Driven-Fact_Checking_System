from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.report_model import VerificationRequest
from agents.orchestrator import run_verification_pipeline
from auth.jwt_handler import decode_access_token
from services.gemini_service import GeminiServiceError
import uuid
from datetime import datetime, timezone

router = APIRouter()
security = HTTPBearer()

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
