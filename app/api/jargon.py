from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from app.database.db import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repo.jargon_repo import get_all_jargon_terms, get_jargon_term

router = APIRouter()

@router.get("/jargon", response_model=List[Dict])
async def list_jargon_terms(db: AsyncIOMotorDatabase = Depends(get_db)):
    return await get_all_jargon_terms(db)

@router.get("/jargon/{term}")
async def fetch_jargon_term(term: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await get_jargon_term(db, term)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Jargon term '{term}' not found")
    return doc