# app/repositories/fe_repo.py
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from app.database.db import get_db

def _normalize(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["_id"] = str(doc["_id"])
    return doc

async def insert_fe_envelope(doc: Dict[str, Any], session_id: str) -> str:
    """Store final FEEnvelope emitted by summariser."""
    db = get_db()
    coll = db["fe_envelopes"]
    to_insert = {**doc}
    to_insert["session_id"] = session_id
    to_insert["created_at"] = datetime.now()
    res = await coll.insert_one(to_insert)
    return str(res.inserted_id)

async def list_by_session(session_id: str) -> List[Dict[str, Any]]:
    """Return all envelopes for a session (latest first)."""
    db = get_db()
    coll = db["fe_envelopes"]
    cursor = coll.find({"session_id": session_id}).sort("created_at", -1)
    out = []
    async for d in cursor:
        out.append(_normalize(d))
    return out

async def get_one(db_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    coll = db["fe_envelopes"]
    d = await coll.find_one({"_id": ObjectId(db_id)})
    return _normalize(d) if d else None

async def get_fe_envelope_by_feature_id(feature_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await db["fe_envelopes"].find_one({"feature_id": feature_id})
    if not doc:
        return None
    doc["db_id"] = str(doc.pop("_id"))
    return doc