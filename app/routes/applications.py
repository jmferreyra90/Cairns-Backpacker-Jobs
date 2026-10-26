
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import CATEGORY_LABELS
from app.database import SessionLocal
from app.models import Business


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MAX_BUSINESSES = 25
MAX_CV_SIZE = 5 * 1024 * 1024  # 5 MB


def get_selected_businesses(raw_ids: str):
    """Retrieve active businesses with contact emails."""

    parts = [part.strip() for part in raw_ids.split(",")]

    if not 1 <= len(parts) <= MAX_BUSINESSES:
        return []

    if any(not part.isascii() or not part.isdigit() for part in parts):
        return []

    selected_ids = list(dict.fromkeys(int(part) for part in parts))

    if any(business_id <= 0 for business_id in selected_ids):
        return []

    with SessionLocal() as db:
        businesses = (
            db.query(Business)
            .filter(
                Business.id.in_(selected_ids),
                Business.active.is_(True),
                Business.email.is_not(None),
                Business.email != "",
            )
            .all()
        )

        business_map = {
            business.id: business for business in businesses
        }

        if len(business_map) != len(selected_ids):
            return []

        return [business_map[id] for id in selected_ids]


def valid_docx(content: bytes) -> bool:
    """Check that the file is a readable Word document package."""

    try:
        with ZipFile(BytesIO(content)) as archive:
            return "word/document.xml" in archive.namelist()
    except BadZipFile:
        return False


def render_compose(request, businesses, error=None, values=None):
    """Display the form, including validation errors."""

    business_ids = ",".join(str(b.id) for b in businesses)

    return templates.TemplateResponse(
        request=request,
        name="compose.html",
        context={
            "businesses": businesses,
            "business_ids": business_ids,
            "category_labels": CATEGORY_LABELS,
            "error": error,
            "form_values": values or {},
        },
        status_code=400 if error else 200,
        headers={"Cache-Control": "no-store"},
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
    subject: str = Form(...),
    cover_letter: str = Form(...),
    cv: UploadFile = File(...),
    phone: str = Form(""),
):

    businesses = get_selected_businesses(business_ids)

    full_name = full_name.strip()
    phone = phone.strip()
    subject = subject.strip()
    cover_letter = cover_letter.strip()

    values = {
        "full_name": full_name,
        "phone": phone,
        "subject": subject,
        "cover_letter": cover_letter,
    }

    error = None
    filename = (cv.filename or "").replace("\\", "/").split("/")[-1]
    extension = Path(filename).suffix.lower()
    content = b""

    try:
        if not businesses:
            error = "La selección de lugares no es válida."

        elif not (
            1 <= len(full_name) <= 100
            and len(phone) <= 40
            and 1 <= len(subject) <= 150
            and 1 <= len(cover_letter) <= 4000
        ):
            error = "Revisá los campos y sus longitudes."

        elif extension not in (".pdf", ".docx"):
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
        return render_compose(
            request, businesses, error=error, values=values
        )

    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "businesses": businesses,
            "full_name": full_name,
            "phone": phone,
            "subject": subject,
            "cover_letter": cover_letter,
            "cv_filename": filename,
            "cv_size": round(len(content) / 1024, 1),
            "category_labels": CATEGORY_LABELS,
        },
        headers={"Cache-Control": "no-store"},
    )
