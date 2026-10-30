"""LOCAL-ONLY business editor. Not an internet-facing authentication system."""
import hmac
import os
import secrets
from datetime import date, datetime, timezone

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

from app.constants import CATEGORIES, CATEGORY_LABELS, CONTACT_LABELS
from app.database import SessionLocal
from app.models import Business
from app.models_directory import BusinessContactReview
from app.services.directory_import import clean_url, import_new_only, parse_directory_csv, MAX_CSV_BYTES

router = APIRouter(prefix="/admin/businesses")
templates = Jinja2Templates(directory="app/templates")
basic = HTTPBasic()


def admin_only(request: Request, credentials: HTTPBasicCredentials = Depends(basic)):
    if (os.getenv("ENABLE_LOCAL_ADMIN", "false").lower() != "true" or
            not request.client or request.client.host not in ("127.0.0.1", "::1")):
        raise HTTPException(status_code=404, detail="Admin unavailable")
    username = os.getenv("LOCAL_ADMIN_USERNAME", "")
    password = os.getenv("LOCAL_ADMIN_PASSWORD", "")
    valid = (
        username and len(password) >= 20 and
        secrets.compare_digest(credentials.username.encode(), username.encode()) and
        secrets.compare_digest(credentials.password.encode(), password.encode())
    )
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid administrator credentials",
                            headers={"WWW-Authenticate": "Basic"})
    return True


def csrf_token(request: Request):
    if not request.session.get("admin_csrf"):
        request.session["admin_csrf"] = secrets.token_urlsafe(32)
    return request.session["admin_csrf"]


def validate_csrf(request: Request, value: str):
    expected = request.session.get("admin_csrf", "")
    if not expected or not hmac.compare_digest(expected, value):
        raise HTTPException(status_code=403, detail="Invalid form token")


def get_review(db, business_id):
    review = db.get(BusinessContactReview, business_id)
    if not review:
        review = BusinessContactReview(business_id=business_id, status="pending")
        db.add(review)
    return review


def render_form(request, business, review, error=None):
    return templates.TemplateResponse(
        request=request, name="admin_business_form.html",
        context=dict(business=business, review=review, categories=CATEGORIES,
                     statuses=CONTACT_LABELS, csrf=csrf_token(request), error=error),
        status_code=400 if error else 200,
        headers={"Cache-Control": "no-store"},
    )


@router.get("", response_class=HTMLResponse)
def admin_list(request: Request, _: bool = Depends(admin_only)):
    with SessionLocal() as db:
        rows = db.query(Business).order_by(Business.name).limit(2000).all()
        meta = {m.business_id: m for m in db.query(BusinessContactReview).all()}
        records = [{"business": b, "review": meta.get(b.id)} for b in rows]
        return templates.TemplateResponse(
            request=request, name="admin_business_list.html",
            context=dict(records=records, status_labels=CONTACT_LABELS,
                         csrf=csrf_token(request)),
            headers={"Cache-Control": "no-store"},
        )


@router.get("/new", response_class=HTMLResponse)
def new_business(request: Request, _: bool = Depends(admin_only)):
    return render_form(request, None, None)


@router.get("/{business_id}", response_class=HTMLResponse)
def edit_business(request: Request, business_id: int, _: bool = Depends(admin_only)):
    with SessionLocal() as db:
        business = db.get(Business, business_id)
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        return render_form(request, business, db.get(BusinessContactReview, business_id))


@router.post("/save")
def save_business(
    request: Request,
    _: bool = Depends(admin_only),
    csrf: str = Form(""),
    business_id: int = Form(0),
    name: str = Form(""),
    category: str = Form("Hotel"),
    manager_name: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    source_url: str = Form(""),
    evidence: str = Form(""),
    status_choice: str = Form("pending"),
    active: bool = Form(False),
):
    validate_csrf(request, csrf)
    name, manager_name, address, phone = [v.strip() for v in (name, manager_name, address, phone)]
    email, evidence, website = [v.strip() for v in (email, evidence, website)]
    if (not name or len(name) > 150 or category not in CATEGORIES or
            status_choice not in ("pending", "general_only", "portal_only", "blocked") or
            len(manager_name) > 150 or len(address) > 250 or len(phone) > 50 or
            len(email) > 150 or len(website) > 250 or len(evidence) > 1500):
        raise HTTPException(status_code=400, detail="Invalid field values")
    try:
        source_url = clean_url(source_url)
        if website:
            clean_url(website)
        if email:
            email = validate_email(email, check_deliverability=False).normalized.lower()
    except (ValueError, EmailNotValidError):
        raise HTTPException(status_code=400, detail="Invalid email or URL")

    with SessionLocal() as db:
        duplicate = db.query(Business).filter(
            func.lower(Business.name) == name.lower(), Business.category == category,
            Business.id != business_id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="This business and category already exist")
        business = db.get(Business, business_id) if business_id else None
        if business_id and not business:
            raise HTTPException(status_code=404, detail="Business not found")
        if not business:
            business = Business(name=name, category=category, active=active, email_verified=False)
            db.add(business)
            db.flush()
        review = get_review(db, business.id)
        # Saving always revokes previous approval until the manager explicitly re-approves.
        business.name, business.category = name, category
        business.manager_name, business.address, business.phone = manager_name or None, address or None, phone or None
        business.email, business.website, business.active = email or None, website or None, active
        business.email_verified, business.last_verified = False, None
        review.source_url, review.evidence = source_url, evidence or None
        review.status, review.approved_at = status_choice, None
        review.updated_at = datetime.now(timezone.utc)
        db.commit()
        return RedirectResponse(url=f"/admin/businesses/{business.id}", status_code=303)


@router.post("/{business_id}/approve")
def approve_business(request: Request, business_id: int,
                     csrf: str = Form(""), confirmation: bool = Form(False),
                     _: bool = Depends(admin_only)):
    validate_csrf(request, csrf)
    if not confirmation:
        raise HTTPException(status_code=400, detail="Confirm manual review")
    with SessionLocal() as db:
        business = db.get(Business, business_id)
        review = db.get(BusinessContactReview, business_id)
        if (not business or not review or not business.active or not business.email or
                not review.source_url or not review.evidence or len(review.evidence.strip()) < 15):
            raise HTTPException(status_code=400, detail="Add a valid email, source and review notes first")
        if business.email.split("@")[-1].lower() in ("example.com", "example.org", "example.net", "test", "invalid", "localhost"):
            raise HTTPException(status_code=400, detail="Cannot approve sample domains")
        # Manual assertion: only use a recruitment-specific address or explicitly confirmed application channel.
        business.email_verified = True
        business.last_verified = date.today()
        review.status = "approved"
        review.approved_at = datetime.now(timezone.utc)
        review.updated_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(url=f"/admin/businesses/{business_id}", status_code=303)


@router.post("/import")
async def import_directory_csv(
    request: Request, _: bool = Depends(admin_only),
    csrf: str = Form(""), csv_file: UploadFile = File(...),
):
    validate_csrf(request, csrf)
    content = await csv_file.read(MAX_CSV_BYTES + 1)
    await csv_file.close()
    try:
        rows = parse_directory_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    with SessionLocal() as db:
        added, skipped = import_new_only(db, rows, apply=True)
    return RedirectResponse(url=f"/admin/businesses?imported={added}&skipped={skipped}", status_code=303)
