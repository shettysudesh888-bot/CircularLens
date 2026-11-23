import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.document import ActionItem, Activity, Chunk, Document, User
from ..access import document_query_for_user, require_document
from .accounts import admin_user, current_user
from ..services import EmbeddingError, build_analysis, chunk_text, extract_page_chunks, extract_text, parse_deadline, rebuild_semantic_index

router = APIRouter(prefix="/documents", tags=["documents"])
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DEMO_MODE = os.getenv("CIRCULARLENS_DEMO_MODE", "").lower() in {"1", "true", "yes"}
_DEMO_DATA_DIR = (_DATA_DIR / "demo").resolve()
UPLOAD_DIR = Path(os.getenv("CIRCULARLENS_UPLOAD_DIR", str(_DEMO_DATA_DIR / "uploads" if _DEMO_MODE else _DATA_DIR / "uploads"))).resolve()
if _DEMO_MODE:
    try:
        UPLOAD_DIR.relative_to(_DEMO_DATA_DIR)
    except ValueError as exc:
        raise RuntimeError("CIRCULARLENS_DEMO_MODE requires CIRCULARLENS_UPLOAD_DIR under backend/data/demo.") from exc
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


class TextCircular(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    text: str = Field(min_length=10, max_length=250000)
    category: str = Field(default="General", max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=12)


class DeadlineUpdate(BaseModel):
    deadline: datetime | None = None
    confirmed: bool = True


def serialize(document: Document) -> dict:
    return {"id": document.id, "filename": document.filename, "uploaded_at": document.upload_time, "content_type": document.content_type, "page_count": document.page_count, "chunk_count": len(document.chunks), "analysis": document.analysis, "deadline": document.deadline, "deadline_confirmed": document.deadline_confirmed, "category": document.category, "tags": document.tags or [], "version_of_id": document.version_of_id, "index_status": document.index_status}


def persist_document(db: Session, filename: str, text: str, *, user: User, path: str, content_type: str, pages: int, category: str = "General", tags: list[str] | None = None, page_chunks: list[tuple[str, int]] | None = None, index_document: bool = True) -> Document:
    digest = __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()
    duplicate = db.query(Document).filter(Document.content_hash == digest, Document.organization_id == user.organization_id).first()
    if duplicate:
        raise HTTPException(409, {"message": "An identical circular is already indexed.", "existing_document_id": duplicate.id})
    analysis = build_analysis(text)
    document = Document(filename=filename, path=path, content_type=content_type, extracted_text=text, page_count=pages, analysis=analysis, deadline=parse_deadline(analysis.get("deadline_text")), category=category.strip() or "General", tags=[tag.strip() for tag in (tags or []) if tag.strip()], content_hash=digest, owner_user_id=user.id, organization_id=user.organization_id, index_status="indexed" if index_document else "pending")
    db.add(document)
    db.flush()
    for text_chunk, page_number in (page_chunks or [(chunk, 1) for chunk in chunk_text(text)]):
        db.add(Chunk(document_id=document.id, text=text_chunk, page_number=page_number))
    db.add(Activity(event_type="indexed", detail=f"Indexed {filename}", document_id=document.id))
    db.flush()
    if index_document:
        try:
            rebuild_semantic_index(db)
        except EmbeddingError as exc:
            db.rollback()
            raise HTTPException(503, f"Circular was not indexed because semantic embeddings are unavailable: {exc}") from exc
    db.refresh(document)
    return document


@router.post("/upload", status_code=201)
async def upload_document(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(400, "A file name is required.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Only PDF, TXT, and Markdown documents are supported.")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Upload must be 15 MB or smaller.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
    stored_path.write_bytes(content)
    try:
        text, pages = extract_text(stored_path, file.content_type)
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not extract this document: {exc}") from exc
    if not text.strip():
        stored_path.unlink(missing_ok=True)
        raise HTTPException(422, "No selectable text was found in this document.")
    try:
        document = persist_document(db, file.filename, text, user=user, path=str(stored_path), content_type=file.content_type or "application/octet-stream", pages=pages, page_chunks=extract_page_chunks(stored_path, file.content_type))
        db.commit()
        db.refresh(document)
    except EmbeddingError as exc:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise HTTPException(503, f"Circular was not saved because semantic indexing is unavailable: {exc}") from exc
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    return serialize(document)


@router.post("/text", status_code=201)
def create_text_circular(payload: TextCircular, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Create a fully searchable circular directly from pasted text."""
    try:
        document = persist_document(db, payload.title, payload.text, user=user, path="", content_type="text/plain", pages=1, category=payload.category, tags=payload.tags)
        db.commit()
        db.refresh(document)
    except EmbeddingError as exc:
        db.rollback()
        raise HTTPException(503, f"Circular was not saved because semantic indexing is unavailable: {exc}") from exc
    return serialize(document)


@router.get("/list")
def list_documents(query: str | None = Query(default=None, max_length=160), category: str | None = None, tag: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = document_query_for_user(db, user)
    if query:
        items = items.filter(Document.filename.ilike(f"%{query}%") | Document.extracted_text.ilike(f"%{query}%"))
    if category:
        items = items.filter(Document.category == category)
    documents = items.order_by(Document.upload_time.desc()).all()
    if tag:
        documents = [item for item in documents if tag in (item.tags or [])]
    return [serialize(document) for document in documents]


@router.get("/export/deadlines.ics")
def export_deadlines(user: User = Depends(current_user), db: Session = Depends(get_db)):
    events = [doc for doc in document_query_for_user(db, user).all() if doc.deadline]
    body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CircularLens AI//EN"]
    for doc in events:
        stamp = doc.deadline.strftime("%Y%m%d")
        body += ["BEGIN:VEVENT", f"UID:circular-{doc.id}@circularlens", f"DTSTART;VALUE=DATE:{stamp}", f"SUMMARY:Deadline — {doc.filename}", "END:VEVENT"]
    body.append("END:VCALENDAR")
    return Response("\r\n".join(body), media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=circularlens-deadlines.ics"})


@router.get("/{document_id}")
def get_document(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = require_document(db, document_id, user)
    return serialize(document)


@router.get("/{document_id}/preview")
def preview_document(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Serve the original PDF when retained, otherwise a safe extracted-text preview."""
    document = require_document(db, document_id, user)
    path = Path(document.path) if document.path else None
    if path and path.is_file() and document.content_type == "application/pdf":
        return FileResponse(path, media_type="application/pdf", filename=document.filename)
    return {"filename": document.filename, "content_type": document.content_type, "text": document.extracted_text}


@router.patch("/{document_id}/deadline")
def set_deadline(document_id: int, payload: DeadlineUpdate, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    document = require_document(db, document_id, user)
    document.deadline, document.deadline_confirmed = payload.deadline, payload.confirmed
    # A confirmed correction supersedes any earlier unverified deadline copied into
    # pending Action Center items for this circular.
    db.query(ActionItem).filter(
        ActionItem.document_id == document.id, ActionItem.status == "pending"
    ).update({ActionItem.deadline: payload.deadline}, synchronize_session=False)
    db.add(Activity(event_type="deadline_confirmed", detail=f"Updated deadline for {document.filename}", document_id=document.id)); db.commit(); db.refresh(document)
    return serialize(document)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = require_document(db, document_id, user)
    if user.role != "admin" and document.owner_user_id != user.id:
        raise HTTPException(403, "Only the uploader or an administrator can delete this document.")
    path = Path(document.path) if document.path else None
    db.delete(document)
    db.flush()
    try:
        rebuild_semantic_index(db)
    except EmbeddingError as exc:
        db.rollback()
        raise HTTPException(503, f"Document was not removed because the semantic index could not be synchronized: {exc}") from exc
    if path and path.is_file():
        path.unlink(missing_ok=True)
    db.commit()
