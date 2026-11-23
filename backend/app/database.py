import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = Path(__file__).resolve().parents[1]
DEMO_MODE = os.getenv("CIRCULARLENS_DEMO_MODE", "").lower() in {"1", "true", "yes"}
DEMO_DATA_DIR = (BASE_DIR / "data" / "demo").resolve()
_default_db = DEMO_DATA_DIR / "app.db" if DEMO_MODE else BASE_DIR / "data" / "app.db"
DB_PATH = Path(os.getenv("CIRCULARLENS_DB_PATH", str(_default_db))).resolve()

# Demo mode is deliberately fenced off from production.  A typo in a launch
# command must not make a demo seed write into the normal workspace database.
if DEMO_MODE:
    try:
        DB_PATH.relative_to(DEMO_DATA_DIR)
    except ValueError as exc:
        raise RuntimeError("CIRCULARLENS_DEMO_MODE requires CIRCULARLENS_DB_PATH under backend/data/demo.") from exc
os.makedirs(DB_PATH.parent, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_sqlite():
    """Small additive migration for installations created before new fields existed."""
    required = {
        "deadline_confirmed": "BOOLEAN NOT NULL DEFAULT 0",
        "category": "VARCHAR NOT NULL DEFAULT 'General'",
        "tags": "JSON",
        "content_hash": "VARCHAR",
        "version_of_id": "INTEGER",
    }
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns("documents")}
    with engine.begin() as connection:
        for name, definition in required.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE documents ADD COLUMN {name} {definition}"))
    chunk_required = {
        "page_number": "INTEGER NOT NULL DEFAULT 1",
        "embedding_provider": "VARCHAR",
        "embedding_model": "VARCHAR",
        "embedding_dimension": "INTEGER",
        "index_version": "VARCHAR",
    }
    if "chunks" in inspector.get_table_names():
        chunk_existing = {item["name"] for item in inspector.get_columns("chunks")}
        with engine.begin() as connection:
            for name, definition in chunk_required.items():
                if name not in chunk_existing:
                    connection.execute(text(f"ALTER TABLE chunks ADD COLUMN {name} {definition}"))

    # All migrations are additive: existing production rows remain untouched.
    additive = {
        "documents": {
            "owner_user_id": "INTEGER",
            "organization_id": "INTEGER",
            "index_status": "VARCHAR NOT NULL DEFAULT 'indexed'",
        },
        "users": {"token_version": "INTEGER NOT NULL DEFAULT 0"},
        "student_profiles": {
            "display_name": "VARCHAR",
            "institution": "VARCHAR",
            "previous_marks_percentage": "INTEGER",
        },
        "notification_subscriptions": {"user_id": "INTEGER"},
        "user_preferences": {"timezone": "VARCHAR NOT NULL DEFAULT 'UTC'"},
        "action_items": {
            "user_id": "INTEGER",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "action_type": "VARCHAR NOT NULL DEFAULT 'application'",
            "amount": "VARCHAR",
        },
        "in_app_notifications": {
            "action_id": "INTEGER",
            "scheduled_for": "DATETIME",
            "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        },
        "document_reviews": {"created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"},
        "activities": {"created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"},
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in additive.items():
            if table not in inspector.get_table_names():
                continue
            existing = {item["name"] for item in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
