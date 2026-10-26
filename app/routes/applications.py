from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import CATEGORY_LABELS
from app.database import SessionLocal
from app.models import Business


router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/compose", response_class=HTMLResponse)
def compose(request: Request, ids: str = ""):

    selected_ids = list(dict.fromkeys(
        int(value)
        for value in ids.split(",")
        if value.strip().isdigit()
    ))

    with SessionLocal() as db:

        businesses = (
            db.query(Business)
            .filter(
                Business.id.in_(selected_ids),
                Business.active.is_(True),
            )
            .all()
        ) if selected_ids else []

        return templates.TemplateResponse(
            request=request,
            name="compose.html",
            context={
                "businesses": businesses,
                "category_labels": CATEGORY_LABELS,
            },
        )