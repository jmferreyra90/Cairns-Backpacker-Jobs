"""Hosted password-protected preview only. Never store personal information or send mail."""
import hmac
import re
import secrets
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models import Business
from app.models_directory import BusinessContactReview

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
MAX_BUSINESSES = 500
MAX_CV_SIZE = 5 * 1024 * 1024


def _selected(raw_ids: str):
    parts = [p.strip() for p in raw_ids.split(",")]
    if not 1 <= len(parts) <= MAX_BUSINESSES:
        return []
    if any(not p.isascii() or not p.isdigit() for p in parts):
        return []
    ids = list(dict.fromkeys(int(p) for p in parts))
    if not ids or any(i <= 0 for i in ids):
        return []
    with SessionLocal() as db:
        blocked = {
            r.business_id for r in db.query(BusinessContactReview).filter(
                BusinessContactReview.status == "blocked"
            ).all()
        }
        businesses = db.query(Business).filter(
            Business.id.in_(ids), Business.active.is_(True)
        ).all()
        lookup = {b.id: b for b in businesses if b.id not in blocked}
        if len(lookup) != len(ids):
            return []
        # Do not expose actual email or manager_name to the staging template.
        return [
            {"id": lookup[i].id, "name": lookup[i].name,
             "category": lookup[i].category, "address": lookup[i].address}
            for i in ids
        ]


def _token(request: Request):
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return request.session["csrf"]


def _compose(request: Request, businesses, error=None, values=None):
    return templates.TemplateResponse(
        request=request,
        name="staging_compose.html",
        context={
            "businesses": businesses,
            "ids": ",".join(str(b["id"]) for b in businesses),
            "csrf_token": _token(request),
            "error": error,
            "values": values or {},
        },
        status_code=400 if error else 200,
        headers={"Cache-Control": "no-store"},
    )


def _docx_ok(data: bytes) -> bool:
    try:
        with ZipFile(BytesIO(data)) as archive:
            return (
                "word/document.xml" in archive.namelist()
                and "[Content_Types].xml" in archive.namelist()
            )
    except (BadZipFile, ValueError):
        return False


@router.get("/compose", response_class=HTMLResponse)
def compose(request: Request, ids: str = ""):
    return _compose(request, _selected(ids))


@router.post("/compose/review", response_class=HTMLResponse)
async def review(
    request: Request,
    business_ids: str = Form(""),
    csrf_token: str = Form(""),
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    subject: str = Form(""),
    cover_letter: str = Form(""),
    cv: UploadFile | None = File(None),
    test_data_confirmed: bool = Form(False),
):
    businesses = _selected(business_ids)
    full_name, email, phone = full_name.strip(), email.strip(), phone.strip()
    subject, cover_letter = subject.strip(), cover_letter.strip()
    values = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "subject": subject,
        "cover_letter": cover_letter,
    }
    expected = request.session.get("csrf", "")
    error = None
    if not expected or not hmac.compare_digest(expected, csrf_token):
        error = "Sesión vencida o solicitud inválida. Volvé a cargar la página."
    elif not businesses:
        error = "Elegí entre 1 y 500 lugares disponibles para la demostración."
    elif not test_data_confirmed:
        error = "Confirmá que estás usando datos de prueba ficticios."
    elif not 1 <= len(full_name) <= 100:
        error = "Ingresá un nombre de prueba válido."
    elif not re.fullmatch(r"[+0-9()\s-]{6,40}", phone):
        error = "Ingresá un teléfono de prueba válido."
    elif not 1 <= len(subject) <= 150:
        error = "Ingresá un asunto válido."
    elif not 1 <= len(cover_letter) <= 4000:
        error = "Ingresá una carta de hasta 4000 caracteres."
    if not error:
        try:
            email = validate_email(email, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            error = "Ingresá un email de prueba válido."

    filename = (cv.filename or "").replace("\\", "/").split("/")[-1] if cv else ""
    extension = Path(filename).suffix.lower()
    try:
        if not error:
            if not cv or extension not in {".pdf", ".docx"}:
                error = "Subí un archivo de prueba PDF o DOCX."
            else:
                data = await cv.read(MAX_CV_SIZE + 1)
                if not data or len(data) > MAX_CV_SIZE:
                    error = "El archivo debe pesar entre 1 byte y 5 MB."
                elif extension == ".pdf" and not data.startswith(b"%PDF-"):
                    error = "El archivo no parece ser un PDF."
                elif extension == ".docx" and not _docx_ok(data):
                    error = "El archivo no parece ser un DOCX."
    finally:
        if cv:
            await cv.close()

    if error:
        return _compose(request, businesses, error=error, values=values)

    # No DB contact insert, draft storage, emails, files or tokens.
    # Replacing placeholders in plain text is safe with Jinja2 autoescaping.
    previews = []
    for business in businesses:
        greeting = "Dear Hiring Manager,"
        letter = cover_letter.replace("[Business Name]", business["name"])
        letter = letter.replace("[Your Name]", full_name)
        personalized_subject = subject.replace("[Business Name]", business["name"])
        body = f"{greeting}\n\n{letter}\n\nKind regards,\n{full_name}\n{phone}"
        previews.append({
            "business_name": business["name"],
            "subject": personalized_subject,
            "body": body,
            "recipient_label": "Sin envío: contacto no utilizado",
        })

    return templates.TemplateResponse(
        request=request,
        name="staging_review.html",
        context={
            "previews": previews, "full_name": full_name,
            "email": email, "phone": phone, "cv_filename": filename,
        },
        headers={"Cache-Control": "no-store"},
    )
