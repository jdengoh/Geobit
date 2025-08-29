from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.database.db import get_db

COLL = "reviews"

async def insert_review(doc: Dict[str, Any]) -> str:
    """
    Insert a HITL review {feature_id, action, reason, reviewer, session_id}.
    Returns _id as string.
    """
    db = get_db()
    body = {**doc}
    body["created_at"] = datetime.now()
    res = await db[COLL].insert_one(body)
    return str(res.inserted_id)

async def list_reviews_by_feature(feature_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db[COLL].find({"feature_id": feature_id}).sort("created_at", -1)
    out: List[Dict[str, Any]] = []
    async for d in cur:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out