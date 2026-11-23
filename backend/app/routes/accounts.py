"""Account, JWT session, and notification-subscription endpoints."""
import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.document import NotificationSubscription, Organization, User

router = APIRouter(prefix="/accounts", tags=["accounts"])
SECRET = os.getenv("CIRCULARLENS_AUTH_SECRET")
if not SECRET:
    raise RuntimeError("CIRCULARLENS_AUTH_SECRET must be configured outside source control.")
TOKEN_TTL_DAYS = int(os.getenv("CIRCULARLENS_TOKEN_TTL_DAYS", "7"))


class Register(BaseModel):
    organization: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=200)


class Login(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str


class Subscription(BaseModel):
    channel: str = Field(pattern="^(email|webhook)$")
    destination: str = Field(min_length=3, max_length=500)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def digest(password: str) -> str:
    """PBKDF2 storage hash; changing the JWT key does not invalidate passwords."""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), SECRET.encode(), 310_000).hex()


def token_for(user: User) -> str:
    """Create a standards-shaped HS256 JWT without accepting arbitrary claims."""
    now = datetime.now(timezone.utc)
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {
        "sub": str(user.id), "role": user.role, "ver": user.token_version,
        "iat": int(now.timestamp()), "exp": int((now + timedelta(days=TOKEN_TTL_DAYS)).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _b64(hmac.new(SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "A bearer token is required.")
    try:
        header, payload, signature = authorization[7:].split(".")
        expected = _b64(hmac.new(SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise ValueError("signature")
        claims = json.loads(_unb64(payload))
        if claims.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        user = db.get(User, int(claims["sub"]))
        if not user or int(claims.get("ver", -1)) != user.token_version:
            raise ValueError("revoked")
        return user
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(401, "Invalid or expired bearer token.") from exc


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator permission is required.")
    return user


@router.get("/me")
def get_current_user(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role, "organization": user.organization.name if user.organization else None}


@router.post("/register", status_code=201)
def register(payload: Register, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    organization_name = payload.organization.strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists.")
    if db.query(Organization).filter(Organization.name == organization_name).first():
        raise HTTPException(409, "This workspace already exists; request an invitation from its administrator.")
    organization = Organization(name=organization_name)
    db.add(organization)
    db.flush()
    user = User(email=email, password_hash=digest(payload.password), role="member", organization_id=organization.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": token_for(user), "user": {"id": user.id, "email": user.email, "role": user.role, "organization": organization.name}}


@router.post("/login")
def login(payload: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not hmac.compare_digest(user.password_hash, digest(payload.password)):
        raise HTTPException(401, "Invalid email or password.")
    return {"token": token_for(user), "user": {"id": user.id, "email": user.email, "role": user.role}}


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Invalidate all active JWTs for this account without retaining token data."""
    user.token_version += 1
    db.commit()


@router.post("/notifications", status_code=201)
def subscribe(payload: Subscription, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = NotificationSubscription(user_id=user.id, channel=payload.channel, destination=payload.destination)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "channel": item.channel, "destination": item.destination, "enabled": item.enabled,
            "delivery": "Stored. Configure a delivery worker for email or webhooks."}
