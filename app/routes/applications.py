"""Collect an application and preview it; only send a single self-test in M5."""
import hmac
import re
import secrets
from io import BytesIO
from pathlib import Path
from time import time
from zipfile import BadZipFile, ZipFile

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import CATEGORY_LABELS
from app.database import SessionLocal
from app.models import Business
from app.services.email_builder import build_email_preview
from app.services.mail_api import SendError, send_self_test
from app.services.session_store import (
    Draft, begin_sending, clear, finish_sending, get_connection, get_draft, put_draft,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
MAX_BUSINESSES = 25
MAX_CV_SIZE = 5 * 1024 * 1024


def _session(request: Request):
    if "sid" not in request.session:
        request.session["sid"] = secrets.token_urlsafe(32)
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return request.session["sid"], request.session["csrf"]


def _csrf_valid(request: Request, candidate: str) -> bool:
    expected = request.session.get("csrf", "")
    return bool(expected and hmac.compare_digest(expected, candidate))


def get_selected_businesses(raw_ids: str):
    parts = [part.strip() for part in raw_ids.split(",")]
    if not 1 <= len(parts) <= MAX_BUSINESSES:
        return []
    if any(not p.isascii() or not p.isdigit() for p in parts):
        return []
    ids = list(dict.fromkeys(int(p) for p in parts))
    if not ids or any(i <= 0 for i in ids):
        return []
    with SessionLocal() as db:
        businesses = (
            db.query(Business)
            .filter(
                Business.id.in_(ids),
                Business.active.is_(True),
                Business.email.is_not(None),
                Business.email != "",
            )
            .all()
        )
        lookup = {b.id: b for b in businesses}
        if len(lookup) != len(ids):
            return []
        return [lookup[i] for i in ids]


def valid_docx(content: bytes) -> bool:
    try:
        with ZipFile(BytesIO(content)) as archive:
            return "word/document.xml" in archive.namelist()
    except (BadZipFile, ValueError):
        return False


def render_compose(request, businesses, error=None, values=None):
    _, csrf = _session(request)
    return templates.TemplateResponse(
        request=request,
        name="compose.html",
        context={
            "businesses": businesses,
            "business_ids": ",".join(str(b.id) for b in businesses),
            "category_labels": CATEGORY_LABELS,
            "error": error,
            "form_values": values or {},
            "csrf_token": csrf,
        },
        status_code=400 if error else 200,
        headers={"Cache-Control": "no-store"},
    )


def render_review(request: Request, error=None):
    sid, csrf = _session(request)
    draft = get_draft(sid)
    if not draft:
        return HTMLResponse(
            "<h2>La postulación venció. Volvé a completarla.</h2>"
            "<a href='/'>Volver al inicio</a>", status_code=410,
        )
    businesses = get_selected_businesses(",".join(str(x) for x in draft.business_ids))
    if len(businesses) != len(draft.business_ids):
        return HTMLResponse("La selección ya no está disponible.", status_code=410)
    previews = [
        build_email_preview(
            b, draft.full_name, draft.phone, draft.subject, draft.cover_letter
        ) for b in businesses
    ]
    return templates.TemplateResponse(
        request=request, name="review.html",
        context={
            "full_name": draft.full_name,
            "email": draft.email,
            "phone": draft.phone,
            "cv_filename": draft.cv_filename,
            "previews": previews,
            "marketing_opt_in": draft.marketing_opt_in,
            "feedback_opt_in": draft.feedback_opt_in,
            "connection": get_connection(sid),
            "csrf_token": csrf,
            "error": error,
        },
        status_code=400 if error else 200,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/privacidad", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={})


@router.get("/compose", response_class=HTMLResponse)
def compose(request: Request, ids: str = ""):
    return render_compose(request, get_selected_businesses(ids))


@router.post("/compose/review", response_class=HTMLResponse)
async def review_application(
    request: Request,
    business_ids: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    subject: str = Form(...),
    cover_letter: str = Form(...),
    cv: UploadFile = File(...),
    csrf_token: str = Form(""),
    privacy_acknowledged: bool = Form(False),
    marketing_opt_in: bool = Form(False),
    feedback_opt_in: bool = Form(False),
):
    sid, _ = _session(request)
    businesses = get_selected_businesses(business_ids)
    full_name, email, phone = full_name.strip(), email.strip(), phone.strip()
    subject, cover_letter = subject.strip(), cover_letter.strip()
    values = dict(
        full_name=full_name, email=email, phone=phone, subject=subject,
        cover_letter=cover_letter, privacy_acknowledged=privacy_acknowledged,
        marketing_opt_in=marketing_opt_in, feedback_opt_in=feedback_opt_in,
    )
    error = None
    filename = (cv.filename or "").replace("\\", "/").split("/")[-1]
    extension = Path(filename).suffix.lower()
    content = b""
    if not _csrf_valid(request, csrf_token):
        error = "La sesión no es válida. Actualizá la página e intentá de nuevo."
    elif not businesses:
        error = "La selección de lugares no es válida."
    elif not privacy_acknowledged:
        error = "Leé la información de privacidad para continuar."
    elif not 1 <= len(full_name) <= 100:
        error = "Ingresá un nombre válido."
    elif not re.fullmatch(r"[+0-9()\s-]{6,40}", phone):
        error = "Ingresá un número de teléfono válido."
    elif not 1 <= len(subject) <= 150:
        error = "Ingresá un asunto válido."
    elif not 1 <= len(cover_letter) <= 4000:
        error = "La carta debe tener entre 1 y 4000 caracteres."
    if error is None:
        try:
            email = validate_email(email, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            error = "Ingresá una dirección de email válida."
    try:
        if error is None:
            if extension not in (".pdf", ".docx"):
                error = "El CV debe estar en formato PDF o DOCX."
            else:
                content = await cv.read(MAX_CV_SIZE + 1)
                if not content:
                    error = "El archivo está vacío."
                elif len(content) > MAX_CV_SIZE:
                    error = "El CV no puede superar los 5 MB."
                elif extension == ".pdf" and not content.startswith(b"%PDF-"):
                    error = "El archivo no parece ser un PDF válido."
                elif extension == ".docx" and not valid_docx(content):
                    error = "El archivo no parece ser un DOCX válido."
    finally:
        await cv.close()
    if error:
        return render_compose(request, businesses, error=error, values=values)
    draft = Draft(
        business_ids=tuple(b.id for b in businesses),
        full_name=full_name, email=email, phone=phone,
        subject=subject, cover_letter=cover_letter,
        cv_filename=filename, cv_bytes=content,
        marketing_opt_in=marketing_opt_in,
        feedback_opt_in=feedback_opt_in,
        created_at=time(),
    )
    if not put_draft(sid, draft):
        return render_compose(
            request, businesses,
            error="La aplicación tiene demasiadas postulaciones abiertas. Probá más tarde.",
            values=values,
        )
    # No contact or marketing preference is persisted until OAuth verifies
    # ownership of the submitted email address.
    return render_review(request)


@router.get("/compose/ready", response_class=HTMLResponse)
def ready(request: Request):
    return render_review(request)


@router.post("/compose/send-test", response_class=HTMLResponse)
async def send_test(request: Request, csrf_token: str = Form("")):
    if not _csrf_valid(request, csrf_token):
        return HTMLResponse("Solicitud no válida.", status_code=403)
    sid = request.session.get("sid")
    draft, connection = get_draft(sid), get_connection(sid)
    if not draft or not connection:
        return render_review(request, error="Conectá tu cuenta antes de probar el envío.")
    if connection.account_email != draft.email:
        return render_review(request, error="La cuenta conectada no coincide.")
    businesses = get_selected_businesses(",".join(str(i) for i in draft.business_ids))
    if len(businesses) != len(draft.business_ids):
        return render_review(request, error="Algunos destinatarios ya no están disponibles.")
    preview = build_email_preview(
        businesses[0], draft.full_name, draft.phone, draft.subject, draft.cover_letter
    )
    if not begin_sending(sid):
        return render_review(request, error="El envío de prueba ya está en curso.")
    try:
        await send_self_test(connection, draft, preview)
    except SendError as exc:
        return render_review(request, error=str(exc))
    finally:
        finish_sending(sid)
    clear(sid)  # Drop CV and OAuth token from process memory after success.
    return templates.TemplateResponse(
        request=request, name="send_test_result.html",
        context={"connected_email": connection.account_email},
        headers={"Cache-Control": "no-store"},
    )
