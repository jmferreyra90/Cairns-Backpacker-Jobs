from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import CATEGORY_LABELS
from app.database import SessionLocal
from app.models import Business


router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):

    with SessionLocal() as db:

        businesses = (
            db.query(Business)
            .filter(Business.active.is_(True))
            .order_by(Business.name)
            .all()
        )

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "businesses": businesses,
                "category_labels": CATEGORY_LABELS,
            },
        )