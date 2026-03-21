from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth.jwt_handler import decode_access_token
from typing import List

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

@router.get("/")
async def get_history(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    limit: int = 20,
    skip: int = 0
):
    db = get_db(request)
    cursor = db.reports.find(
        {"user_id": user_id},
        {
            "_id": 1,
            "input_type": 1,
            "input_text": 1,
            "source_url": 1,
            "overall_accuracy": 1,
            "total_claims": 1,
            "true_count": 1,
            "false_count": 1,
            "partial_count": 1,
            "hallucination_count": 1,
            "processing_time": 1,
            "created_at": 1
        }
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    reports = []
    async for doc in cursor:
        doc["id"] = doc.pop("_id")
        doc["preview"] = doc.get("input_text", "")[:120] + "..."
        reports.append(doc)
    
    total = await db.reports.count_documents({"user_id": user_id})
    return {"reports": reports, "total": total, "skip": skip, "limit": limit}

@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db(request)
    result = await db.reports.delete_one({"_id": report_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted successfully"}

@router.get("/stats/summary")
async def get_stats(
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db(request)
    
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": None,
            "total_reports": {"$sum": 1},
            "avg_accuracy": {"$avg": "$overall_accuracy"},
            "total_claims": {"$sum": "$total_claims"},
            "total_hallucinations": {"$sum": "$hallucination_count"},
            "total_false": {"$sum": "$false_count"},
            "total_true": {"$sum": "$true_count"},
        }}
    ]
    
    results = []
    async for doc in db.reports.aggregate(pipeline):
        results.append(doc)
    
    if not results:
        return {
            "total_reports": 0,
            "avg_accuracy": 0,
            "total_claims": 0,
            "total_hallucinations": 0,
            "total_false": 0,
            "total_true": 0
        }
    
    stats = results[0]
    stats.pop("_id", None)
    return stats
