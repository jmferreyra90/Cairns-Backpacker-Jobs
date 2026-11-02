"""Supabase magic-link Auth API and opaque server-side browser sessions.

Only use in private staging with STAGING_ENABLE_ACCOUNTS=true.
Never put access tokens into cookies, logs, URLs or database rows.
"""
import hashlib
import os
import secrets
from datetime import timedelta, timezone

import httpx
from fastapi import Request
from sqlalchemy.orm import Session

from app.models_accounts import ApplicantAccount, ErasureRequest, WebSession, utc_now

COOKIE_NAME = "cairns_verified_session"
SESSION_HOURS = 12


def _settings():
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_PUBLISHABLE_KEY"]
    if not base.startswith("https://") or ".supabase.co" not in base:
        raise RuntimeError("Invalid Supabase Auth project URL")
    return base, key


def _headers():
    _, key = _settings()
    return {"apikey": key, "Content-Type": "application/json"}


class AuthServiceError(Exception):
    pass


def request_magic_link(email: str, state: str):
    """Ask Supabase to email its built-in one-time sign-in link."""
    base, _ = _settings()
    callback_url = os.environ["APP_PUBLIC_URL"].rstrip("/") + "/cuenta/callback?state=" + state
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                base + "/auth/v1/otp",
                headers=_headers(),
                params={"redirect_to": callback_url},
                json={
                    "email": email,
                    "create_user": True,
                },
            )
        if response.status_code >= 400:
            raise AuthServiceError("No se pudo solicitar el enlace. Revisá los límites de Supabase Auth.")
    except httpx.RequestError as exc:
        raise AuthServiceError("El servicio de acceso no está disponible.") from exc


def identity_from_access_token(access_token: str):
    """Validate Google/Microsoft-independent Supabase Auth access token on its server."""
    base, _ = _settings()
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(
                base + "/auth/v1/user",
                headers={**_headers(), "Authorization": "Bearer " + access_token},
            )
        if response.status_code != 200:
            raise AuthServiceError("El enlace no es válido o venció.")
        identity = response.json()
        if not identity.get("id") or not identity.get("email"):
            raise AuthServiceError("No se pudo comprobar la identidad del usuario.")
        if not identity.get("email_confirmed_at"):
            raise AuthServiceError("La dirección todavía no fue verificada.")
        return {"id": identity["id"], "email": identity["email"].strip().lower()}
    except (httpx.RequestError, ValueError) as exc:
        raise AuthServiceError("No se pudo verificar el acceso.") from exc


def start_web_session(db: Session, identity: dict):
    account = db.get(ApplicantAccount, identity["id"])
    if db.query(ErasureRequest).filter(ErasureRequest.account_id == identity["id"], ErasureRequest.resolved.is_(False)).first():
        raise AuthServiceError("Esta cuenta tiene una solicitud de eliminación pendiente.")
    if account is None:
        account = ApplicantAccount(id=identity["id"], email=identity["email"])
        db.add(account)
    else:
        account.email = identity["email"]
    raw = secrets.token_urlsafe(48)
    db.add(WebSession(
        token_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        account_id=account.id,
        expires_at=utc_now() + timedelta(hours=SESSION_HOURS),
    ))
    db.commit()
    return raw


def current_account(db: Session, request: Request):
    raw = request.cookies.get(COOKIE_NAME, "")
    if not 20 <= len(raw) <= 200:
        return None
    session = db.get(WebSession, hashlib.sha256(raw.encode()).hexdigest())
    if session is None:
        return None
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= utc_now():
        return None
    return db.get(ApplicantAccount, session.account_id)


def revoke_session(db: Session, request: Request):
    raw = request.cookies.get(COOKIE_NAME, "")
    if raw:
        session = db.get(WebSession, hashlib.sha256(raw.encode()).hexdigest())
        if session:
            db.delete(session)
            db.commit()


def set_session_cookie(response, raw: str):
    response.set_cookie(
        COOKIE_NAME, raw,
        httponly=True,
        secure=True,  # Accounts are enabled only for HTTPS hosted staging.
        samesite="lax", max_age=SESSION_HOURS * 3600, path="/",
    )


def clear_session_cookie(response):
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
