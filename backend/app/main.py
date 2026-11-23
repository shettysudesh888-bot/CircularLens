import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, migrate_sqlite
from .models import document  # Register model metadata before creating tables.
from .routes import accounts, documents, chat, analytics, comparison, rag, intelligence, academic, guest
from .reminders import ReminderScheduler

app = FastAPI(title="CircularLens AI", version="0.1.0")
reminder_scheduler = ReminderScheduler()

@app.on_event("startup")
def initialize_database():
    Base.metadata.create_all(bind=engine)
    migrate_sqlite()
    if os.getenv("CIRCULARLENS_ENABLE_REMINDER_SCHEDULER", "true").lower() in {"1", "true", "yes"}:
        reminder_scheduler.start()


@app.on_event("shutdown")
def stop_reminder_scheduler():
    reminder_scheduler.stop()

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

# Allow all origins for local dev; tighten in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(analytics.router)
app.include_router(comparison.router)
app.include_router(accounts.router)
app.include_router(rag.router)
app.include_router(intelligence.router)
app.include_router(academic.router)
app.include_router(guest.router)
