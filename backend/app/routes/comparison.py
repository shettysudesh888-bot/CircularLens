import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.document import Activity, Document
from ..access import require_document
from .accounts import User, current_user

router = APIRouter(prefix="/comparison", tags=["comparison"])

class ComparisonRequest(BaseModel):
    left_document_id: int
    right_document_id: int

def keywords(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-zA-Z]{4,}", text.lower()) if word not in {"that", "this", "with", "from", "will", "have", "shall", "their", "which", "under"}}

@router.post("/compare")
def compare_documents(request: ComparisonRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    left, right = require_document(db, request.left_document_id, user), require_document(db, request.right_document_id, user)
    left_words, right_words = keywords(left.extracted_text), keywords(right.extracted_text)
    shared = sorted(left_words & right_words)[:30]
    union = left_words | right_words
    similarity = round((len(left_words & right_words) / len(union) * 100) if union else 0, 1)
    left_dates = set((left.analysis or {}).get("key_dates", []))
    right_dates = set((right.analysis or {}).get("key_dates", []))
    db.add(Activity(event_type="comparison", detail=f"Compared {left.filename} with {right.filename}", document_id=left.id))
    db.commit()
    return {"similarity_percent": similarity, "shared_keywords": shared, "only_in_left": sorted(left_words - right_words)[:30], "only_in_right": sorted(right_words - left_words)[:30], "dates": {"shared": sorted(left_dates & right_dates), "only_in_left": sorted(left_dates - right_dates), "only_in_right": sorted(right_dates - left_dates)}}
