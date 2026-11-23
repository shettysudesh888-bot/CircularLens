from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..access import document_query_for_user
from ..models.document import Document
from .accounts import User, admin_user, current_user
from ..services import EmbeddingError, INDEX_PATH, ensure_semantic_index, rebuild_semantic_index, require_faiss

router = APIRouter(prefix="/rag", tags=["semantic-rag"])

@router.get("/diagnostics")
def diagnostics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        config = ensure_semantic_index(db)
        index = require_faiss().read_index(str(INDEX_PATH))
        scoped = document_query_for_user(db, user)
        pending = scoped.filter(Document.index_status == "pending").count()
        return {"provider": config["provider"], "model": config["model"], "dimension": config["dimension"], "normalization": config["normalization"], "index_version": config["index_version"], "indexed_document_count": scoped.count() - pending, "pending_document_count": pending, "indexed_chunk_count": int(index.ntotal), "index_health": "pending_documents" if pending else ("healthy" if int(index.ntotal) == config["chunk_count"] else "count_mismatch")}
    except EmbeddingError as exc:
        return {"index_health": "unavailable", "detail": str(exc)}

@router.post("/reindex")
def reindex(provider: str | None = None, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    try:
        return rebuild_semantic_index(db, provider)
    except EmbeddingError as exc:
        raise HTTPException(503, str(exc)) from exc
