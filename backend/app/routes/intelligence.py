"""Action Center, evidence review, drafts, and user-scoped reminders."""
import json
import time
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..access import document_query_for_user, require_document
from ..database import get_db
from ..models.document import ActionItem, DocumentReview, InAppNotification, UserPreference
from ..reminders import cancel_action_reminders, schedule_due_reminders
from ..services import classify_circular, gemini_client, generate_with_retry
from .accounts import User, admin_user, current_user

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

# Minimal standard-library fallback for Windows Python installations that lack
# the IANA zoneinfo database. Additional IANA IDs still require system tzdata.
WINDOWS_TIMEZONE_FALLBACKS = {
    "UTC": timezone.utc,
    "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30)),
    "Asia/Calcutta": timezone(timedelta(hours=5, minutes=30)),
}


class ActionUpdate(BaseModel):
    # "completed" is student-reported completion, not university confirmation.
    status: str | None = Field(default=None, pattern="^(pending|in_progress|completed|dismissed|needs_verification)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")
    title: str | None = Field(default=None, min_length=3, max_length=200)


class ReviewInput(BaseModel):
    field_name: str = Field(min_length=2, max_length=80)
    value: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(default="", max_length=4000)
    verified: bool = True


class PreferencesInput(BaseModel):
    departments: list[str] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)
    semesters: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    bookmarks: list[int] = Field(default_factory=list)
    timezone: str = Field(default="UTC", max_length=80)


def action_payload(item: ActionItem) -> dict:
    return {
        "id": item.id, "document_id": item.document_id,
        "document_name": item.document.filename if item.document else "Circular",
        "title": item.title, "description": item.description, "deadline": item.deadline,
        "priority": item.priority, "status": item.status, "evidence": item.evidence,
        "ai_suggested": item.ai_suggested, "verified": item.verified_by_user_id is not None,
        "action_type": item.action_type, "amount": item.amount,
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


def _action_warranted(analysis: dict) -> bool:
    category = str(analysis.get("category") or "").lower()
    return category in {"application", "payment", "scholarship", "submission", "examination"} and bool(analysis.get("actions"))


def _create_action_for_document(user: User, document, db: Session) -> ActionItem | None:
    analysis = document.analysis or {}
    if not _action_warranted(analysis):
        return None
    title = f"Review requirements for {document.filename}"
    existing = db.query(ActionItem).filter(
        ActionItem.user_id == user.id, ActionItem.document_id == document.id, ActionItem.title == title
    ).first()
    if existing:
        return None
    action_text = "; ".join(str(item) for item in (analysis.get("actions") or [])[:3])
    item = ActionItem(
        user_id=user.id, document_id=document.id, title=title,
        description=action_text or "Review this circular and complete any applicable requirement.",
        deadline=document.deadline, priority="high" if document.deadline else "medium",
        evidence=str(analysis.get("summary") or "")[:500], ai_suggested=True,
        action_type="payment" if str(analysis.get("category") or "").lower() == "payment" else "application",
        amount=str(analysis.get("fees")) if analysis.get("fees") is not None else None,
    )
    db.add(item)
    return item



@router.post("/classify/{document_id}")
def classify_document(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Classify a circular and create a private action only when action is warranted."""
    document = require_document(db, document_id, user)
    try:
        analysis = classify_circular(document.extracted_text or "")
    except Exception as exc:
        raise HTTPException(502, f"Gemini classification failed: {exc}") from exc
    document.analysis = analysis
    document.category = str(analysis.get("category") or "General").title()
    # Gemini proposals are evidence to review, never confirmed operational deadlines.
    document.deadline_confirmed = False
    created_action = _create_action_for_document(user, document, db)
    db.commit()
    db.refresh(document)
    return {"id": document.id, "category": document.category, "analysis": document.analysis,
            "deadline": document.deadline, "deadline_confirmed": document.deadline_confirmed,
            "action_created": bool(created_action)}


@router.post("/actions/generate")
def generate_actions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Backfill current user's Action Center from already-classified accessible documents."""
    created: list[ActionItem] = []
    for document in document_query_for_user(db, user).all():
        item = _create_action_for_document(user, document, db)
        if item:
            created.append(item)
    db.commit()
    for item in created:
        db.refresh(item)
    return {"created": len(created), "actions": [action_payload(item) for item in created]}


@router.get("/actions")
def list_actions(status: str | None = Query(default=None, pattern="^(pending|completed|dismissed)$"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(ActionItem).filter(ActionItem.user_id == user.id)
    if status:
        query = query.filter(ActionItem.status == status)
    return [action_payload(item) for item in query.order_by(ActionItem.deadline.asc(), ActionItem.created_at.desc()).all()]


@router.patch("/actions/{action_id}")
def update_action(action_id: int, payload: ActionUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.query(ActionItem).filter(ActionItem.id == action_id, ActionItem.user_id == user.id).first()
    if not item:
        raise HTTPException(404, "Action not found.")
    for name, value in payload.model_dump(exclude_none=True).items():
        setattr(item, name, value)
    if item.status in {"completed", "dismissed"}:
        # Pending reminders are no longer relevant, while action history remains.
        cancel_action_reminders(db, item.id, user.id)
    if user.role == "admin":
        item.verified_by_user_id = user.id
    db.commit()
    db.refresh(item)
    return action_payload(item)


@router.post("/draft/{document_id}")
def generate_draft(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Generate an editable draft from an accessible circular; never add personal facts."""
    document = require_document(db, document_id, user)
    analysis = document.analysis
    if not analysis:
        try:
            analysis = classify_circular(document.extracted_text or "")
        except Exception as exc:
            raise HTTPException(502, f"Gemini classification failed: {exc}") from exc
        document.analysis = analysis
        document.category = str(analysis.get("category") or "General").title()
        db.commit()
    prompt = (
        "Draft an editable university application or letter from the supplied circular analysis. "
        "Use only stated purpose, eligibility, required_documents, fees, actions, and deadlines. "
        "Do not invent student identity, facts, approval, payment, or attachments."
    )
    try:
        response, model = generate_with_retry(contents=[prompt, json.dumps(analysis)], client=gemini_client())
    except Exception as exc:
        raise HTTPException(502, f"Gemini draft generation failed: {exc}") from exc
    return {"document_id": document.id, "draft": response.text or "", "generation_model": model}


@router.post("/notifications/generate")
def generate_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Manual recovery hook; the internal scheduler performs normal delivery."""
    return {"created": schedule_due_reminders(db, user_id=user.id)}


@router.get("/documents/{document_id}/evidence")
def evidence(document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = require_document(db, document_id, user)
    reviews = db.query(DocumentReview).filter(DocumentReview.document_id == document_id).order_by(DocumentReview.created_at.desc()).all()
    return {"document_id": document.id, "filename": document.filename, "preview_available": bool(document.path),
            "analysis": document.analysis or {}, "deadline": document.deadline,
            "deadline_confirmed": document.deadline_confirmed,
            "reviews": [{"id": item.id, "field_name": item.field_name, "value": item.value, "evidence": item.evidence,
                         "verified": item.verified, "created_at": item.created_at} for item in reviews]}


@router.post("/documents/{document_id}/reviews", status_code=201)
def review(document_id: int, payload: ReviewInput, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    require_document(db, document_id, user)
    item = DocumentReview(document_id=document_id, reviewer_id=user.id, **payload.model_dump())
    db.add(item)
    db.add(InAppNotification(user_id=None, kind="review", title="Circular analysis reviewed",
                             body=f"{payload.field_name} was reviewed by an administrator.", document_id=document_id))
    db.commit()
    db.refresh(item)
    return {"id": item.id, "verified": item.verified}


@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": item.id, "kind": item.kind, "title": item.title, "body": item.body,
             "document_id": item.document_id, "read": item.read, "created_at": item.created_at}
            for item in db.query(InAppNotification).filter(InAppNotification.user_id == user.id)
            .order_by(InAppNotification.created_at.desc()).limit(50)]


@router.patch("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.query(InAppNotification).filter(InAppNotification.id == notification_id, InAppNotification.user_id == user.id).first()
    if not item:
        raise HTTPException(404, "Notification not found.")
    item.read = True
    db.commit()
    return {"id": item.id, "read": True}


@router.get("/preferences")
def preferences(user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    return ({"departments": item.departments, "programs": item.programs, "semesters": item.semesters,
             "categories": item.categories, "bookmarks": item.bookmarks, "timezone": item.timezone}
            if item else PreferencesInput().model_dump())


@router.put("/preferences")
def update_preferences(payload: PreferencesInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        # Windows Python installations may not ship the IANA zone database.
        # Keep the supported local fallback explicit rather than accepting an
        # arbitrary string that the scheduler cannot evaluate.
        if payload.timezone not in WINDOWS_TIMEZONE_FALLBACKS:
            raise HTTPException(422, "timezone must be a valid IANA timezone.") from exc
    item = db.query(UserPreference).filter(UserPreference.user_id == user.id).first() or UserPreference(user_id=user.id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    return payload.model_dump()
