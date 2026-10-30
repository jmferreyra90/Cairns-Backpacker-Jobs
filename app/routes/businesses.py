"""Cairns business directory. Staging is explicitly read-only and hides contacts."""
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import CATEGORY_LABELS
from app.database import SessionLocal
from app.models import Business
from app.models_directory import BusinessContactReview

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
        if os.getenv("APP_MODE", "local").lower() == "staging":
            # No email addresses, managers, or applicant information in the preview.
            public_rows = [
                {"name": b.name, "category": b.category, "address": b.address}
                for b in businesses
            ]
            return templates.TemplateResponse(
                request=request,
                name="staging_directory.html",
                context={"businesses": public_rows, "category_labels": CATEGORY_LABELS},
                headers={"Cache-Control": "no-store"},
            )

        review_map = {r.business_id: r for r in db.query(BusinessContactReview).all()}
        rows = [
            {"business": b, "status": review_map[b.id].status if b.id in review_map else "pending",
             "selectable": bool(b.email) and (b.id not in review_map or review_map[b.id].status != "blocked")}
            for b in businesses
        ]
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"rows": rows, "category_labels": CATEGORY_LABELS},
        )
