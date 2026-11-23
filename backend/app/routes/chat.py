from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.document import Activity
from ..access import document_query_for_user
from .accounts import User, current_user
from ..services import EmbeddingError, gemini_answer, semantic_search

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    query: str = Field(min_length=3, max_length=3000)
    document_ids: list[int] | None = None

@router.post("/query")
def chat_query(request: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    allowed_ids = {document.id for document in document_query_for_user(db, user).all()}
    requested_ids = set(request.document_ids or allowed_ids)
    if not requested_ids or not requested_ids.issubset(allowed_ids):
        raise HTTPException(404, "One or more documents were not found.")
    try:
        context = semantic_search(db, request.query, document_ids=list(requested_ids))
    except EmbeddingError as exc:
        raise HTTPException(503, f"Semantic retrieval is unavailable: {exc}") from exc
    if not context:
        raise HTTPException(404, "Upload a searchable document before asking a question.")
    try:
        answer, model = gemini_answer(request.query, context, include_model=True)
    except Exception as exc:
        raise HTTPException(502, f"Gemini request failed: {exc}") from exc
    db.add(Activity(event_type="query", detail=request.query[:180], document_id=context[0]["document_id"]))
    db.commit()
    return {"answer": answer, "sources": context, "generation_model": model}
