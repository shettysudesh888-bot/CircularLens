"""Import the existing fictional 60-circular corpus into the normal app.

This is deliberately *not* demo mode: it uses the configured production
SQLite, Gemini embedding provider, FAISS index, and normal authentication
models. It writes only the requested dummy workspace and takes a timestamped
database/index backup before any mutation. If Gemini embedding is unavailable,
the command stops before creating the dummy account or documents.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if os.getenv("CIRCULARLENS_DEMO_MODE", "").lower() in {"1", "true", "yes"}:
    raise SystemExit("This importer targets normal application storage. Unset CIRCULARLENS_DEMO_MODE.")
if os.getenv("CIRCULARLENS_EMBEDDING_PROVIDER", "gemini").lower() != "gemini":
    raise SystemExit("This importer requires the genuine configured Gemini embedding provider; do not use deterministic-demo.")

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DB = ROOT / "backend" / "data" / "demo" / "app.db"
EMAIL = "demo.data.science@demo-university.example"
PASSWORD = os.getenv("CIRCULARLENS_DEMO_PASSWORD")
WORKSPACE = "Demo University — Data Science"

from backend.app.database import Base, DB_PATH, SessionLocal, engine, migrate_sqlite
from backend.app.models.document import (ActionItem, CircularRelationship, Document,
                                         InAppNotification, Organization, StudentProfile,
                                         User, UserPreference)
from backend.app.reminders import schedule_due_reminders
from backend.app.routes.accounts import digest
from backend.app.routes.documents import persist_document
from backend.app.routes.intelligence import _create_action_for_document
from backend.app.services import EmbeddingError, EmbeddingService, INDEX_DIR, INDEX_PATH


def _source_records() -> list[dict]:
    if not SOURCE_DB.exists():
        raise RuntimeError(f"The reusable fictional source corpus is missing: {SOURCE_DB}")
    source = sqlite3.connect(SOURCE_DB)
    source.row_factory = sqlite3.Row
    try:
        records = [dict(row) for row in source.execute(
            "SELECT filename, extracted_text, category, tags FROM documents "
            "WHERE filename LIKE 'DU-%' ORDER BY filename"
        )]
    finally:
        source.close()
    if len(records) != 60:
        raise RuntimeError(f"Expected exactly 60 source circulars, found {len(records)}.")
    for record in records:
        record["tags"] = json.loads(record["tags"] or "[]")
    return records


def _backup() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = DB_PATH.parent / "backups" / f"dummy-workspace-import-{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(DB_PATH, target / "app.db")
    if INDEX_DIR.exists():
        shutil.copytree(INDEX_DIR, target / "semantic_index")
    (target / "manifest.json").write_text(json.dumps({
        "created_at": datetime.now().isoformat(), "source_database": str(DB_PATH),
        "source_index": str(INDEX_PATH), "purpose": "pre-import backup for dummy workspace seed",
    }, indent=2), encoding="utf-8")
    return target


def _fixture_analysis(document: Document) -> dict:
    """Visible, honest source-derived fixture needed for deterministic actions.

    It deliberately does not mimic a Gemini result and keeps every deadline
    unverified. Live classification can subsequently replace this data only
    when Gemini is available.
    """
    title = document.filename.removesuffix(".txt")
    category = {
        "Scholarship applications": "scholarship", "Examination notices": "examination",
        "Payment and fee circulars": "payment", "Academic submissions": "submission",
        "Placement/internship opportunities": "application", "Events and workshops": "event",
        "Informational notices": "informational", "Policy amendments and deadline extensions": "policy",
        "Cancelled/superseded notices": "policy", "Ambiguous/incomplete notices": "application",
    }.get(document.category, "general")
    actionable = category in {"scholarship", "examination", "payment", "submission", "application"} and document.category not in {"Cancelled/superseded notices"}
    fee_match = __import__("re").search(r"Fee information:\s*([^\n.]+)", document.extracted_text or "", __import__("re").I)
    documents_match = __import__("re").search(r"Required documents:\s*([^\n.]+)", document.extracted_text or "", __import__("re").I)
    return {
        "category": category,
        "summary": f"Demo fixture, not Gemini: source circular {title} is available for review.",
        "actions": ["Review the source circular and complete the stated requirement."] if actionable else [],
        "fees": fee_match.group(1).strip() if fee_match else None,
        "required_documents": [item.strip() for item in documents_match.group(1).split(",")] if documents_match else [],
        "analysis_source": "human_authored_demo_fixture_not_gemini",
        "verified": False,
    }


def _relationship_pairs(documents: dict[str, Document]) -> list[tuple[str, str, str]]:
    return [
        ("DU-AMD-1001.txt", "DU-FEE-501.txt", "EXTENDS"), ("DU-AMD-1002.txt", "DU-EXM-404.txt", "AMENDS"),
        ("DU-AMD-1003.txt", "DU-EXM-403.txt", "CLARIFIES"), ("DU-AMD-1004.txt", "DU-SUB-601.txt", "EXTENDS"),
        ("DU-AMD-1005.txt", "DU-PLC-701.txt", "AMENDS"), ("DU-AMD-1006.txt", "DU-SCH-307.txt", "EXTENDS"),
        ("DU-AMD-1007.txt", "DU-FEE-508.txt", "CLARIFIES"), ("DU-CAN-1101.txt", "DU-PLC-706.txt", "CANCELS"),
        ("DU-CAN-1102.txt", "DU-EXM-404.txt", "SUPERSEDES"), ("DU-CAN-1103.txt", "DU-FEE-506.txt", "CANCELS"),
    ]


def run(*, allow_pending_index: bool = False) -> dict:
    if not PASSWORD:
        raise RuntimeError("Set CIRCULARLENS_DEMO_PASSWORD locally before importing a dummy workspace.")
    # Preflight is intentionally before account creation/backup/import. A
    # failure here means no normal-app state was modified.
    pending_index = False
    try:
        EmbeddingService("gemini").document_vectors(["CircularLens normal workspace import preflight."])
    except EmbeddingError:
        if not allow_pending_index:
            raise
        pending_index = True
    records = _source_records()
    backup = _backup()
    Base.metadata.create_all(bind=engine); migrate_sqlite()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == EMAIL).first()
        if user and user.organization and user.organization.name != WORKSPACE:
            raise RuntimeError("The requested dummy email already belongs to a different workspace; refusing to repurpose it.")
        if not user:
            workspace = db.query(Organization).filter(Organization.name == WORKSPACE).first()
            if workspace:
                raise RuntimeError("The requested demo workspace already exists without its expected dummy user; refusing to attach to it.")
            workspace = Organization(name=WORKSPACE); db.add(workspace); db.flush()
            user = User(email=EMAIL, password_hash=digest(PASSWORD), organization_id=workspace.id, role="member"); db.add(user); db.flush()
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first() or StudentProfile(user_id=user.id)
        profile.display_name, profile.institution = "Demo Data Science Student", "Demo University"
        profile.program, profile.department, profile.semester = "MSc Data Science", "Data Science", 3
        profile.attendance_percentage, profile.backlog_count, profile.previous_marks_percentage, profile.condonation_approved = 86, 0, 82, None
        preference = db.query(UserPreference).filter(UserPreference.user_id == user.id).first() or UserPreference(user_id=user.id)
        preference.departments, preference.programs, preference.semesters, preference.timezone = ["Data Science"], ["MSc Data Science"], ["3"], "Asia/Kolkata"
        db.add_all([profile, preference]); db.commit(); db.refresh(user)

        created = 0
        for record in records:
            document = db.query(Document).filter(Document.organization_id == user.organization_id, Document.filename == record["filename"]).first()
            if not document:
                document = persist_document(db, record["filename"], record["extracted_text"], user=user, path="", content_type="text/plain", pages=1, category=record["category"], tags=record["tags"], index_document=not pending_index)
                created += 1
            document.category = record["category"]
            document.analysis = _fixture_analysis(document)
            document.deadline_confirmed = False
            db.commit(); db.refresh(document)
            _create_action_for_document(user, document, db); db.commit()

        documents = {item.filename: item for item in db.query(Document).filter(Document.organization_id == user.organization_id).all()}
        for source_name, target_name, relationship_type in _relationship_pairs(documents):
            source, target = documents[source_name], documents[target_name]
            existing = db.query(CircularRelationship).filter(CircularRelationship.source_document_id == source.id, CircularRelationship.target_document_id == target.id, CircularRelationship.relationship_type == relationship_type).first()
            if not existing:
                db.add(CircularRelationship(source_document_id=source.id, target_document_id=target.id, relationship_type=relationship_type, scope={}, evidence="Demo fixture relationship; administrator review required.", verified=False))
        db.commit()
        actions = db.query(ActionItem).filter(ActionItem.user_id == user.id).order_by(ActionItem.id).all()
        for position, action in enumerate(actions):
            if position < 3: action.status = "completed"
            elif position < 5: action.status = "in_progress"
            elif position == 5: action.status = "dismissed"
        db.commit(); schedule_due_reminders(db, user_id=user.id)
        if not db.query(InAppNotification).filter(InAppNotification.user_id == user.id, InAppNotification.kind == "demo").first():
            db.add(InAppNotification(user_id=user.id, kind="demo", title="Welcome to the dummy workspace", body="All documents are fictional. Fixture summaries are not Gemini output.")); db.commit()
        return {"backup": str(backup), "workspace": WORKSPACE, "email": EMAIL, "created_documents": created, "total_documents": len(documents), "actions": len(actions), "index": str(INDEX_PATH), "index_status": "pending" if pending_index else "indexed"}
    finally:
        db.close()


if __name__ == "__main__":
    try:
        print(json.dumps(run(allow_pending_index="--allow-unindexed-fixtures" in sys.argv), indent=2))
    except EmbeddingError as exc:
        raise SystemExit(f"Import stopped before mutation: Gemini embedding preflight failed: {exc}. To persist clearly marked unindexed fixtures, use --allow-unindexed-fixtures.") from exc
