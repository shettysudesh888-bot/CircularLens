"""Safely index normal-app dummy workspace documents with live Gemini vectors.

The active FAISS index is shared by design, so rebuilding refreshes all existing
chunks atomically; document access remains enforced by query-time workspace
authorization. The script marks dummy rows indexed only after FAISS succeeds.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

if os.getenv("CIRCULARLENS_DEMO_MODE", "").lower() in {"1", "true", "yes"}:
    raise SystemExit("Unset CIRCULARLENS_DEMO_MODE; this targets the normal application.")

from backend.app.database import DB_PATH, SessionLocal
from backend.app.models.document import Document, User
from backend.app.services import EmbeddingError, INDEX_DIR, INDEX_PATH, rebuild_semantic_index, semantic_search

EMAIL = "demo.data.science@demo-university.example"


def backup() -> Path:
    target = DB_PATH.parent / "backups" / f"live-gemini-reindex-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(DB_PATH, target / "app.db")
    if INDEX_DIR.exists(): shutil.copytree(INDEX_DIR, target / "semantic_index")
    return target


def run() -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == EMAIL).first()
        if not user: raise RuntimeError("Dummy workspace user does not exist.")
        dummy_docs = db.query(Document).filter(Document.organization_id == user.organization_id).all()
        if len(dummy_docs) != 60: raise RuntimeError(f"Expected 60 dummy documents, found {len(dummy_docs)}.")
        saved = backup()
        def progress(done: int, total: int) -> None: print(f"embedding progress {done}/{total}", flush=True)
        metadata = rebuild_semantic_index(db, "gemini", batch_size=10, progress=progress)
        for item in dummy_docs: item.index_status = "indexed"
        db.commit()
        result = semantic_search(db, "semester three tuition instalment payment deadline", limit=3, document_ids=[item.id for item in dummy_docs])
        return {"backup": str(saved), "indexed_dummy_documents": len(dummy_docs), "index_chunks": metadata["chunk_count"], "provider": metadata["provider"], "retrieval": result}
    finally:
        db.close()


if __name__ == "__main__":
    try: print(json.dumps(run(), indent=2, default=str))
    except EmbeddingError as exc: raise SystemExit(f"Reindex failed; previous index/data retained: {exc}") from exc
