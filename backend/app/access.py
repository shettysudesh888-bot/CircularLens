"""Authorization helpers shared by document-facing routes."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models.document import Document, User


def can_access_document(document: Document, user: User) -> bool:
    """Keep documents inside a workspace; legacy rows are admin-review only."""
    if document.organization_id is None:
        return user.role == "admin"
    return document.organization_id == user.organization_id


def require_document(db: Session, document_id: int, user: User) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found.")
    if not can_access_document(document, user):
        # Return 404 so IDs cannot be used to enumerate other tenants' documents.
        raise HTTPException(404, "Document not found.")
    return document


def document_query_for_user(db: Session, user: User):
    if user.role == "admin":
        return db.query(Document).filter(
            (Document.organization_id == user.organization_id) | (Document.organization_id.is_(None))
        )
    return db.query(Document).filter(Document.organization_id == user.organization_id)
