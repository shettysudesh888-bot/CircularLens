"""CLI-only CircularLens administrator provisioning.

There is intentionally no HTTP endpoint for this operation.  An operator must
either authenticate with an existing admin bearer token or explicitly perform a
one-time bootstrap using a secret that is already configured in the local
environment.  Every successful action is recorded in the normal activity log.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import os
import sys

from backend.app.database import SessionLocal
from backend.app.models.document import Activity, Organization, User
from backend.app.routes.accounts import current_user, digest


def _password(args: argparse.Namespace) -> str:
    if args.password_env:
        value = os.getenv(args.password_env)
        if not value:
            raise SystemExit(f"Password environment variable {args.password_env!r} is not set.")
        return value
    first = getpass.getpass("New administrator password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        raise SystemExit("Passwords did not match.")
    return first


def _operator(db, args: argparse.Namespace) -> str:
    if args.operator_token:
        user = current_user(f"Bearer {args.operator_token}", db)
        if user.role != "admin":
            raise SystemExit("Operator token belongs to a non-administrator.")
        return f"admin:{user.id}"
    if not args.bootstrap:
        raise SystemExit("Provide --operator-token for an existing admin, or use explicit --bootstrap.")
    configured = os.getenv("CIRCULARLENS_ADMIN_BOOTSTRAP_SECRET")
    if not configured:
        raise SystemExit("Bootstrap is disabled: CIRCULARLENS_ADMIN_BOOTSTRAP_SECRET is not configured.")
    supplied = os.getenv("CIRCULARLENS_ADMIN_BOOTSTRAP_INPUT") or getpass.getpass("Bootstrap secret: ")
    if not hmac.compare_digest(hashlib.sha256(supplied.encode()).digest(), hashlib.sha256(configured.encode()).digest()):
        raise SystemExit("Bootstrap secret did not match.")
    return "bootstrap:" + hashlib.sha256(configured.encode()).hexdigest()[:12]


def run(args: argparse.Namespace) -> dict:
    email = args.email.strip().lower()
    if len(args.password) < 10:
        raise SystemExit("Administrator password must contain at least 10 characters.")
    db = SessionLocal()
    try:
        actor = _operator(db, args)
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role != "admin":
                raise SystemExit("Refusing to elevate an existing member. Create a distinct administrator identity.")
            return {"created": False, "email": email, "user_id": existing.id, "organization_id": existing.organization_id}
        workspace = db.query(Organization).filter(Organization.name == args.workspace).first()
        if not workspace:
            raise SystemExit("Workspace does not exist; provisioning does not create workspaces.")
        user = User(email=email, password_hash=digest(args.password), organization_id=workspace.id, role="admin")
        db.add(user); db.flush()
        db.add(Activity(event_type="admin_provisioned", detail=f"actor={actor}; user_id={user.id}; workspace_id={workspace.id}"))
        db.commit()
        return {"created": True, "email": email, "user_id": user.id, "organization_id": workspace.id}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a CircularLens administrator without an HTTP route.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--operator-token", help="Existing administrator bearer token; never store it in scripts.")
    parser.add_argument("--bootstrap", action="store_true", help="Use only for deliberate first-admin bootstrap.")
    parser.add_argument("--password-env", help="Read the new password from this process-local environment variable.")
    args = parser.parse_args()
    args.password = _password(args)
    result = run(args)
    print(f"created={result['created']} email={result['email']} user_id={result['user_id']} organization_id={result['organization_id']}")


if __name__ == "__main__":
    main()
