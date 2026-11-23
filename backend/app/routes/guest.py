"""Short-lived, isolated guest AI workspace APIs.

Guest material lives only in process memory. It is intentionally excluded from
the production document tables, FAISS index, organizations, profiles, and RAG.
"""
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import fitz
from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ..services import classify_circular, gemini_answer

router = APIRouter(prefix="/guest", tags=["guest-workspace"])
SESSION_TTL_SECONDS = 60 * 60
MAX_TEXT_CHARS = 100_000
MAX_UPLOAD_BYTES = 1_000_000
MAX_REQUESTS_PER_HOUR = 30
MAX_SESSIONS_PER_HOUR = 10


@dataclass
class GuestSession:
    token: str
    created_at: datetime
    expires_at: datetime
    text: str = ""
    filename: str = "Guest circular"
    analysis: dict = field(default_factory=dict)


class GuestStore:
    def __init__(self):
        self._sessions: dict[str, GuestSession] = {}
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _clean(self) -> None:
        now = datetime.now(timezone.utc)
        self._sessions = {token: value for token, value in self._sessions.items() if value.expires_at > now}
        cutoff = time.time() - 3600
        for key, events in list(self._requests.items()):
            while events and events[0] < cutoff:
                events.popleft()
            if not events:
                self._requests.pop(key, None)

    def rate_limit(self, client_key: str, limit: int) -> None:
        with self._lock:
            self._clean()
            events = self._requests[client_key]
            if len(events) >= limit:
                raise HTTPException(429, "Guest request limit reached. Please try again later or sign in.")
            events.append(time.time())

    def create(self) -> GuestSession:
        with self._lock:
            self._clean()
            now = datetime.now(timezone.utc)
            session = GuestSession(token=secrets.token_urlsafe(24), created_at=now, expires_at=now + timedelta(seconds=SESSION_TTL_SECONDS))
            self._sessions[session.token] = session
            return session

    def get(self, token: str | None) -> GuestSession:
        with self._lock:
            self._clean()
            session = self._sessions.get(token or "")
            if not session:
                raise HTTPException(401, "Guest session is missing or expired. Start a new guest session.")
            return session


store = GuestStore()


class GuestText(BaseModel):
    text: str = Field(min_length=10, max_length=MAX_TEXT_CHARS)
    title: str = Field(default="Guest circular", min_length=1, max_length=160)


class GuestQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)


def _client_key(request: Request, scope: str) -> str:
    return f"{scope}:{request.client.host if request.client else 'unknown'}"


def _session(guest_session: str | None) -> GuestSession:
    return store.get(guest_session)


def _analyze(session: GuestSession) -> dict:
    try:
        analysis = classify_circular(session.text)
    except Exception as exc:
        raise HTTPException(502, f"Guest AI analysis is temporarily unavailable: {type(exc).__name__}.") from exc
    session.analysis = analysis
    return {"filename": session.filename, "analysis": analysis, "expires_at": session.expires_at,
            "notice": "Guest content is temporary and is not added to your library, reminders, or profile."}


@router.post("/sessions", status_code=201)
def create_session(request: Request):
    store.rate_limit(_client_key(request, "sessions"), MAX_SESSIONS_PER_HOUR)
    session = store.create()
    return {"guest_session": session.token, "expires_at": session.expires_at,
            "notice": "Guest sessions are temporary. Conversation history and reminders are not saved."}


@router.post("/text/analyze")
def analyze_text(payload: GuestText, request: Request, x_guest_session: str | None = Header(default=None)):
    store.rate_limit(_client_key(request, "requests"), MAX_REQUESTS_PER_HOUR)
    session = _session(x_guest_session)
    session.text, session.filename = payload.text.strip(), payload.title.strip()
    return _analyze(session)


@router.post("/upload/analyze")
async def analyze_upload(request: Request, file: UploadFile = File(...), x_guest_session: str | None = Header(default=None)):
    store.rate_limit(_client_key(request, "requests"), MAX_REQUESTS_PER_HOUR)
    session = _session(x_guest_session)
    suffix = (file.filename or "").lower().rsplit(".", 1)[-1]
    if suffix not in {"pdf", "txt", "md"}:
        raise HTTPException(415, "Guest uploads support PDF, TXT, and Markdown only.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Guest upload must be between 1 byte and 1 MB.")
    try:
        if suffix == "pdf":
            pdf = fitz.open(stream=content, filetype="pdf")
            try:
                text = "\n".join(page.get_text("text") for page in pdf)
            finally:
                pdf.close()
        else:
            text = content.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(422, "Could not read the guest document.") from exc
    if len(text.strip()) < 10:
        raise HTTPException(422, "Guest document contains no usable text.")
    session.text, session.filename = text[:MAX_TEXT_CHARS], file.filename or "Guest circular"
    return _analyze(session)


@router.post("/chat")
def chat(payload: GuestQuestion, request: Request, x_guest_session: str | None = Header(default=None)):
    store.rate_limit(_client_key(request, "requests"), MAX_REQUESTS_PER_HOUR)
    session = _session(x_guest_session)
    if not session.text:
        raise HTTPException(409, "Add a temporary circular before asking a question.")
    source = {"source_name": session.filename, "document_id": "guest", "page_number": 1, "text": session.text[:MAX_TEXT_CHARS]}
    try:
        answer = gemini_answer(payload.question, [source])
    except Exception as exc:
        raise HTTPException(502, f"Guest AI chat is temporarily unavailable: {type(exc).__name__}.") from exc
    return {"answer": answer, "sources": [{"source_name": session.filename, "page_number": 1}],
            "notice": "This guest conversation is temporary and not saved."}
