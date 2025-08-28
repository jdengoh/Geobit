from typing import List, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

async def get_all_jargon_terms(db: AsyncIOMotorDatabase) -> List[Dict]:
    """
    Fetch all jargon terms from the `jargon_terms` collection.
    """
    cursor = db["jargon_terms"].find({})
    results = []
    async for doc in cursor:
        # Convert ObjectId to string if needed
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results

async def get_jargon_term(db: AsyncIOMotorDatabase, term: str) -> Optional[Dict]:
    """
    Fetch a single jargon term by its `term` field.
    Returns None if not found.
    """
    doc = await db["jargon_terms"].find_one({"term": term})
    if doc:
        doc["_id"] = str(doc["_id"])  # convert ObjectId
    return doc