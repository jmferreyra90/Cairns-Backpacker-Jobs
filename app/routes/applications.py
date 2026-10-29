
import re
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import CATEGORY_LABELS
from app.database import SessionLocal
from app.models import Business
from app.services.contacts import save_applicant_contact
from app.services.email_builder import build_email_preview


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MAX_BUSINESSES = 25
MAX_CV_SIZE = 5 * 1024 * 1024


def get_selected_businesses(raw_ids: str):
    """Return active businesses with usable contact emails."""

    parts = [part.strip() for part in raw_ids.split(",")]

    if not 1 <= len(parts) <= MAX_BUSINESSES:
        return []

    if any(not p.isascii() or not p.isdigit() for p in parts):
        return []

    ids = list(dict.fromkeys(int(p) for p in parts))

    if any(business_id <= 0 for business_id in ids):
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

        business_map = {b.id: b for b in businesses}

        if len(business_map) != len(ids):
            return []

        return [business_map[id] for id in ids]


def valid_docx(content: bytes) -> bool:
    """Check the expected structure of a DOCX file."""

    try:
        with ZipFile(BytesIO(content)) as archive:
            return "word/document.xml" in archive.namelist()
    except BadZipFile:
        return False


def render_compose(request, businesses, error=None, values=None):
    """Render the application form."""

    ids = ",".join(str(b.id) for b in businesses)

    return templates.TemplateResponse(
        request=request,
        name="compose.html",
        context={
            "businesses": businesses,
            "business_ids": ids,
            "category_labels": CATEGORY_LABELS,
            "error": error,
            "form_values": values or {},
        },
        status_code=400 if error else 200,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/privacidad", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="privacy.html",
        context={},
    )


@router.get("/compose", response_class=HTMLResponse)
def compose(request: Request, ids: str = ""):

    businesses = get_selected_businesses(ids)

    return render_compose(request, businesses)


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
    privacy_acknowledged: bool = Form(False),
    marketing_opt_in: bool = Form(False),
    feedback_opt_in: bool = Form(False),
):

    businesses = get_selected_businesses(business_ids)

    full_name = full_name.strip()
    email = email.strip()
    phone = phone.strip()
    subject = subject.strip()
    cover_letter = cover_letter.strip()

    values = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "subject": subject,
        "cover_letter": cover_letter,
        "privacy_acknowledged": privacy_acknowledged,
        "marketing_opt_in": marketing_opt_in,
        "feedback_opt_in": feedback_opt_in,
    }

    error = None
    filename = (cv.filename or "").replace("\\", "/").split("/")[-1]
    extension = Path(filename).suffix.lower()
    content = b""

    # Validate selected businesses and contact information.
    if not businesses:
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
            email = validate_email(
                email,
                check_deliverability=False,
            ).normalized.lower()

        except EmailNotValidError:
            error = "Ingresá una dirección de email válida."

    # Validate the CV without keeping it permanently.
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

                elif (
                    extension == ".pdf"
                    and not content.startswith(b"%PDF-")
                ):
                    error = "El archivo no parece ser un PDF válido."

                elif extension == ".docx" and not valid_docx(content):
                    error = "El archivo no parece ser un DOCX válido."

    finally:
        await cv.close()

    if error:
        return render_compose(
            request,
            businesses,
            error=error,
            values=values,
        )

    # Persist contact information after successful validation.
    with SessionLocal() as db:
        save_applicant_contact(
            db=db,
            full_name=full_name,
            email=email,
            phone=phone,
            marketing_opt_in=marketing_opt_in,
            feedback_opt_in=feedback_opt_in,
        )

    # Generate one email preview for each selected business.
    previews = [
        build_email_preview(
            business=business,
            full_name=full_name,
            phone=phone,
            subject=subject,
            cover_letter=cover_letter,
        )
        for business in businesses
    ]

    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "cv_filename": filename,
            "previews": previews,
            "marketing_opt_in": marketing_opt_in,
            "feedback_opt_in": feedback_opt_in,
        },
        headers={"Cache-Control": "no-store"},
    )
