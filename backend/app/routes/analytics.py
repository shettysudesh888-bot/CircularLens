from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.document import ActionItem, Activity, Document, InAppNotification
from ..access import document_query_for_user
from .accounts import User, current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/stats")
def get_stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    documents = document_query_for_user(db, user).all()
    document_ids = [item.id for item in documents]
    upcoming = [d for d in documents if d.deadline and now <= d.deadline <= now + timedelta(days=30)]
    activities = (db.query(Activity).filter(Activity.document_id.in_(document_ids)).order_by(Activity.created_at.desc()).limit(12).all() if document_ids else [])
    scoped = db.query(Activity).filter(Activity.document_id.in_(document_ids)) if document_ids else db.query(Activity).filter(False)
    return {"total_documents": len(documents), "total_queries": scoped.filter(Activity.event_type == "query").count(), "total_comparisons": scoped.filter(Activity.event_type == "comparison").count(), "upcoming_deadlines": [{"document_id": d.id, "filename": d.filename, "deadline": d.deadline} for d in sorted(upcoming, key=lambda item: item.deadline)], "recent_activity": [{"type": item.event_type, "detail": item.detail, "created_at": item.created_at} for item in activities]}


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Return only factual, user-scoped Action Center data.

    The overview intentionally has a deterministic fallback: it must remain
    truthful when Gemini is unavailable and must never manufacture tasks.
    """
    now = datetime.utcnow()
    documents = document_query_for_user(db, user).order_by(Document.upload_time.desc()).all()
    actions = db.query(ActionItem).filter(ActionItem.user_id == user.id).order_by(ActionItem.deadline.asc(), ActionItem.created_at.desc()).all()
    active_statuses = {"pending", "in_progress", "needs_verification"}
    active_actions = [item for item in actions if item.status in active_statuses]
    completed_actions = [item for item in actions if item.status == "completed"]
    actionable = [item for item in active_actions if item.action_type != "payment"]
    payments = [item for item in active_actions if item.action_type == "payment"]
    upcoming = [item for item in active_actions if item.deadline and now <= item.deadline <= now + timedelta(days=30)]
    unread = db.query(InAppNotification).filter(InAppNotification.user_id == user.id, InAppNotification.read.is_(False)).count()

    if not documents:
        overview = "No circulars are in this workspace yet. Upload an official circular to begin source-grounded analysis."
    elif active_actions:
        overview = f"{len(active_actions)} active action{'s' if len(active_actions) != 1 else ''} are linked to your circulars. Review source evidence before treating AI-extracted details as confirmed."
    else:
        overview = f"{len(documents)} circular{'s' if len(documents) != 1 else ''} are available. No action-bearing requirement is currently pending."

    def action_value(item: ActionItem) -> dict:
        derived_status = "overdue" if item.status in active_statuses and item.deadline and item.deadline < now else item.status
        return {
            "id": item.id, "document_id": item.document_id,
            "document_name": item.document.filename if item.document else "Circular",
            "title": item.title, "description": item.description,
            "deadline": item.deadline, "priority": item.priority,
            "status": derived_status, "stored_status": item.status,
            "action_type": item.action_type, "amount": item.amount,
            "verified": item.verified_by_user_id is not None,
        }

    return {
        "overview": {"text": overview, "source": "deterministic_workspace_data"},
        "metrics": {
            "active_circulars": len(documents), "pending_applications": len(actionable),
            "pending_payments": len(payments), "upcoming_deadlines": len(upcoming),
            "completed_actions": len(completed_actions), "unread_notifications": unread,
        },
        "circulars": [{
            "id": item.id, "filename": item.filename, "category": item.category,
            "uploaded_at": item.upload_time, "deadline": item.deadline,
            "deadline_confirmed": item.deadline_confirmed,
            "summary": (item.analysis or {}).get("summary") or "No AI summary is available yet.",
            "status": "deadline confirmed" if item.deadline_confirmed else "analysis requires review",
        } for item in documents[:8]],
        "actions": [action_value(item) for item in active_actions[:10]],
        "completed": [action_value(item) for item in completed_actions[:10]],
        "notifications": [{
            "id": item.id, "title": item.title, "body": item.body, "kind": item.kind,
            "read": item.read, "created_at": item.created_at, "document_id": item.document_id,
        } for item in db.query(InAppNotification).filter(InAppNotification.user_id == user.id).order_by(InAppNotification.created_at.desc()).limit(8)],
    }
