"""Business directory: local app or strictly no-send hosted staging demo."""
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
        review_map = {r.business_id: r.status for r in db.query(BusinessContactReview).all()}

        if os.getenv("APP_MODE", "local").lower() == "staging":
            allow_demo = os.getenv("STAGING_ENABLE_FORMS", "false").lower() == "true"
            # Only public information leaves the server; emails and manager names stay private.
            public_rows = [
                {
                    "id": b.id,
                    "name": b.name,
                    "category": b.category,
                    "address": b.address,
                    "selectable": allow_demo and review_map.get(b.id) != "blocked",
                }
                for b in businesses
            ]
            return templates.TemplateResponse(
                request=request,
                name="staging_directory.html",
                context={
                    "businesses": public_rows,
                    "category_labels": CATEGORY_LABELS,
                    "demo_enabled": allow_demo,
                    "accounts_enabled": os.getenv("STAGING_ENABLE_ACCOUNTS", "false").lower() == "true",
                },
                headers={"Cache-Control": "no-store"},
            )

        rows = [
            {
                "business": b,
                "status": review_map.get(b.id, "pending"),
                "selectable": bool(b.email) and review_map.get(b.id) != "blocked",
            }
            for b in businesses
        ]
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"rows": rows, "category_labels": CATEGORY_LABELS},
        )


@router.get("/privacidad", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={},
                                      headers={"Cache-Control": "no-store"})
