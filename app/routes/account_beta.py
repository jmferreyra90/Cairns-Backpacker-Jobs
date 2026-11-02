"""Verified profiles and draft text, only in password-protected staging.

This router DOES NOT accept CVs or send email.
"""
import hmac
import hashlib
import os
import re
import secrets
from datetime import datetime, timezone

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import delete

from app.database import SessionLocal
from app.models import Business
from app.models_directory import BusinessContactReview
from app.models_accounts import ApplicantAccount, ApplicationDraft, ErasureRequest, WebSession
from app.models_draft_ops import DraftCV, DraftSimulation
from app.services.private_cv import remove_private, CVStorageError
from app.services.account_auth import (
    AuthServiceError, clear_session_cookie, current_account, identity_from_access_token,
    request_magic_link, revoke_session, set_session_cookie, start_web_session,
)

router = APIRouter(prefix="/cuenta")
templates = Jinja2Templates(directory="app/templates")
PRIVACY_VERSION = "2026-11-beta2"
FILE_BETA = os.getenv("STAGING_ENABLE_DRAFT_FILES", "false").lower() == "true"


def csrf(request: Request):
    if "account_csrf" not in request.session:
        request.session["account_csrf"] = secrets.token_urlsafe(32)
    return request.session["account_csrf"]


def valid_csrf(request: Request, submitted: str):
    expected = request.session.get("account_csrf", "")
    return bool(expected and hmac.compare_digest(expected, submitted))


def page(request, template, status_code=200, **context):
    return templates.TemplateResponse(
        request=request, name=template, context={"csrf_token": csrf(request), **context},
        status_code=status_code, headers={"Cache-Control": "no-store"},
    )


def redirect(where):
    return RedirectResponse(where, status_code=303, headers={"Cache-Control": "no-store"})


def require_user(request, db):
    return current_account(db, request)


@router.get("", response_class=HTMLResponse)
def account_home(request: Request, notice: str = ""):
    with SessionLocal() as db:
        account = require_user(request, db)
        drafts = []
        if account:
            drafts = db.query(ApplicationDraft).filter(
                ApplicationDraft.account_id == account.id
            ).order_by(ApplicationDraft.updated_at.desc()).limit(30).all()
            return page(request, "account_home.html", account=account, drafts=drafts, notice=notice)
    return page(request, "account_login.html", notice=notice)


@router.post("/enlace")
def request_link(request: Request, email: str = Form(""), csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return page(request, "account_login.html", error="Sesión vencida. Recargá la página.", status_code=400)
    try:
        normalized = validate_email(email.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return page(request, "account_login.html", error="Ingresá un email válido.", status_code=400)
    nonce = secrets.token_urlsafe(32)
    request.session["login_state"] = nonce
    request.session["pending_email_tag"] = hmac.new(
        os.environ["APP_SESSION_SECRET"].encode(), normalized.encode(), hashlib.sha256
    ).hexdigest()
    try:
        request_magic_link(normalized, nonce)
    except AuthServiceError as exc:
        request.session.pop("login_state", None)
        request.session.pop("pending_email_tag", None)
        return page(request, "account_login.html", error=str(exc), status_code=429)
    return page(request, "account_login.html", sent=True)


@router.get("/callback", response_class=HTMLResponse)
def account_callback(request: Request, state: str = ""):
    expected = request.session.get("login_state", "")
    if not state or not expected or not hmac.compare_digest(state, expected):
        return page(request, "account_login.html", error="Abrí el enlace en el mismo navegador donde lo solicitaste.", status_code=400)
    return page(request, "account_callback.html", state=state)


class CallbackPayload(BaseModel):
    state: str = Field(min_length=15, max_length=200)
    csrf_token: str = Field(min_length=15, max_length=200)
    access_token: str = Field(min_length=40, max_length=8000)


@router.post("/confirmar")
def confirm_callback(request: Request, payload: CallbackPayload):
    expected = request.session.get("login_state", "")
    if not valid_csrf(request, payload.csrf_token) or not expected or not hmac.compare_digest(expected, payload.state):
        return JSONResponse({"error": "Sesión de inicio inválida."}, status_code=403)
    # One-time state: even a failed attempt cannot replay this callback.
    request.session.pop("login_state", None)
    email_tag = request.session.pop("pending_email_tag", "")
    try:
        identity = identity_from_access_token(payload.access_token)
        verified_tag = hmac.new(
            os.environ["APP_SESSION_SECRET"].encode(), identity["email"].encode(), hashlib.sha256
        ).hexdigest()
        if not email_tag or not hmac.compare_digest(email_tag, verified_tag):
            raise AuthServiceError("El email verificado no coincide con el solicitado.")
        with SessionLocal() as db:
            raw = start_web_session(db, identity)
    except AuthServiceError:
        return JSONResponse({"error": "No se pudo comprobar tu email."}, status_code=401)
    response = JSONResponse({"ok": True, "next": "/cuenta"}, headers={"Cache-Control": "no-store"})
    set_session_cookie(response, raw)
    return response


@router.post("/salir")
def sign_out(request: Request, csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return redirect("/cuenta")
    with SessionLocal() as db:
        revoke_session(db, request)
    response = redirect("/cuenta")
    clear_session_cookie(response)
    return response


@router.post("/perfil")
def update_profile(
    request: Request,
    full_name: str = Form(""), phone: str = Form(""),
    marketing_opt_in: bool = Form(False), feedback_opt_in: bool = Form(False),
    privacy_acknowledged: bool = Form(False), csrf_token: str = Form(""),
):
    if not valid_csrf(request, csrf_token):
        return redirect("/cuenta")
    full_name, phone = full_name.strip(), phone.strip()
    if not privacy_acknowledged or not 1 <= len(full_name) <= 100 or not re.fullmatch(r"[+0-9()\s-]{6,40}", phone):
        return page(request, "account_error.html", message="Revisá tu nombre, teléfono y la información de privacidad.", status_code=400)
    with SessionLocal() as db:
        account = require_user(request, db)
        if not account:
            return redirect("/cuenta")
        now = datetime.now(timezone.utc)
        if marketing_opt_in and not account.marketing_opt_in:
            account.marketing_consented_at = now
        elif not marketing_opt_in:
            account.marketing_consented_at = None
        if feedback_opt_in and not account.feedback_opt_in:
            account.feedback_consented_at = now
        elif not feedback_opt_in:
            account.feedback_consented_at = None
        account.full_name = full_name
        account.phone = phone
        account.marketing_opt_in = marketing_opt_in
        account.feedback_opt_in = feedback_opt_in
        account.privacy_notice_version = PRIVACY_VERSION
        account.updated_at = now
        db.commit()
    return redirect("/cuenta?notice=perfil-guardado")


def available_businesses(db):
    blocked = {r.business_id for r in db.query(BusinessContactReview).filter(BusinessContactReview.status == "blocked").all()}
    return [b for b in db.query(Business).filter(Business.active.is_(True)).order_by(Business.name).all() if b.id not in blocked]


@router.get("/borradores/nuevo", response_class=HTMLResponse)
def new_draft(request: Request):
    with SessionLocal() as db:
        account = require_user(request, db)
        if not account:
            return redirect("/cuenta")
        if not account.full_name or not account.phone:
            return redirect("/cuenta?notice=completa-perfil")
        names = [{"id": b.id, "name": b.name} for b in available_businesses(db)]
    return page(request, "account_new_draft.html", businesses=names)


@router.post("/borradores")
def save_draft(
    request: Request, business_ids: list[int] = Form([]),
    subject: str = Form(""), cover_letter: str = Form(""), csrf_token: str = Form(""),
):
    if not valid_csrf(request, csrf_token):
        return redirect("/cuenta")
    subject, cover_letter = subject.strip(), cover_letter.strip()
    ids = list(dict.fromkeys(business_ids))
    if not 1 <= len(ids) <= 10 or any(i <= 0 for i in ids) or not 1 <= len(subject) <= 150 or not 1 <= len(cover_letter) <= 4000:
        return page(request, "account_error.html", message="Elegí 1 a 10 lugares y completá el asunto y la carta.", status_code=400)
    with SessionLocal() as db:
        account = require_user(request, db)
        if not account or not account.full_name or not account.phone:
            return redirect("/cuenta")
        valid = {b.id for b in available_businesses(db)}
        if not set(ids).issubset(valid):
            return page(request, "account_error.html", message="Hay lugares que ya no están disponibles.", status_code=400)
        draft = ApplicationDraft(account_id=account.id, business_ids=ids, subject=subject, cover_letter=cover_letter)
        db.add(draft)
        db.commit()
        draft_id = draft.id
    return redirect("/cuenta/borradores/" + draft_id)


@router.get("/borradores/{draft_id}", response_class=HTMLResponse)
def view_draft(request: Request, draft_id: str):
    with SessionLocal() as db:
        account = require_user(request, db)
        if not account:
            return redirect("/cuenta")
        draft = db.get(ApplicationDraft, draft_id)
        if not draft or draft.account_id != account.id:
            return page(request, "account_error.html", message="Borrador no encontrado.", status_code=404)
        businesses = db.query(Business).filter(Business.id.in_(draft.business_ids)).all()
        business_map = {b.id: b for b in businesses}
        # Data materialized while session is open.
        previews = []
        for business_id in draft.business_ids:
            b = business_map.get(business_id)
            if not b:
                continue
            letter = draft.cover_letter.replace("[Business Name]", b.name).replace("[Your Name]", account.full_name)
            subject = draft.subject.replace("[Business Name]", b.name)
            previews.append({"business": b.name, "subject": subject,
                             "body": f"Dear Hiring Manager,\n\n{letter}\n\nKind regards,\n{account.full_name}\n{account.phone}"})
        attachment = db.query(DraftCV).filter(DraftCV.draft_id == draft.id).first() if FILE_BETA else None
        simulation = db.query(DraftSimulation).filter(DraftSimulation.draft_id == draft.id).first() if FILE_BETA else None
        file_info = None
        if attachment:
            expires = attachment.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            file_info = {"filename": attachment.filename, "size_bytes": attachment.size_bytes,
                         "expired": expires <= datetime.now(timezone.utc)}
        simulation_id = simulation.id if simulation else None
    return page(request, "account_draft.html", draft_id=draft_id, previews=previews,
                file_info=file_info, simulation_id=simulation_id, file_beta=FILE_BETA)


@router.post("/borradores/{draft_id}/eliminar")
def delete_draft(request: Request, draft_id: str, csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return redirect("/cuenta")
    with SessionLocal() as db:
        account = require_user(request, db)
        if not account:
            return redirect("/cuenta")
        draft = db.get(ApplicationDraft, draft_id)
        if not draft or draft.account_id != account.id:
            return page(request, "account_error.html", message="Borrador no encontrado.", status_code=404)
        attached = db.query(DraftCV).filter(DraftCV.draft_id == draft.id).first() if FILE_BETA else None
        if attached:
            try:
                remove_private(attached.storage_path)
            except CVStorageError:
                return page(request, "account_error.html",
                            message="No pudimos eliminar el archivo del borrador. Intentá de nuevo.", status_code=502)
        db.delete(draft)
        db.commit()
    return redirect("/cuenta?notice=borrador-eliminado")


@router.post("/solicitar-eliminacion")
def request_erasure(request: Request, csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return redirect("/cuenta")
    with SessionLocal() as db:
        account = require_user(request, db)
        if not account:
            return redirect("/cuenta")
        pending = db.query(ErasureRequest).filter(
            ErasureRequest.account_id == account.id, ErasureRequest.resolved.is_(False)
        ).first()
        if not pending:
            db.add(ErasureRequest(account_id=account.id, email=account.email))
        files = ((db.query(DraftCV).join(ApplicationDraft, DraftCV.draft_id == ApplicationDraft.id)
                 .filter(ApplicationDraft.account_id == account.id).all()) if FILE_BETA else [])
        try:
            for cv in files:
                remove_private(cv.storage_path)
        except CVStorageError:
            return page(request, "account_error.html",
                        message="No se pudieron borrar todos los archivos. Reintentá tu solicitud.", status_code=502)
        account.full_name = ""
        account.phone = ""
        account.marketing_opt_in = False
        account.feedback_opt_in = False
        account.marketing_consented_at = None
        account.feedback_consented_at = None
        db.execute(delete(ApplicationDraft).where(ApplicationDraft.account_id == account.id))
        db.execute(delete(WebSession).where(WebSession.account_id == account.id))
        db.commit()
    response = page(request, "account_error.html", message="Solicitud registrada. Tus borradores se eliminaron y se cerraron tus sesiones. El perfil y la identidad en Supabase requieren revisión manual para su eliminación completa.")
    clear_session_cookie(response)
    return response
