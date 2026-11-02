"""Private CV test uploads and DB-backed simulation queue for verified accounts.

Absolutely no employer email routes or message APIs are used here.
"""
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile, BadZipFile

from fastapi import APIRouter, Form, Request, UploadFile, File, Header, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Business
from app.models_accounts import ApplicationDraft
from app.models_draft_ops import DraftCV, DraftSimulation, DraftSimulationItem, utc_now
from app.services.account_auth import current_account
from app.services.private_cv import upload_private, remove_private, CVStorageError

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
MAX_CV = 5 * 1024 * 1024
CV_LIFETIME = timedelta(hours=24)
MAINTENANCE_PATH = "/internal/cleanup-expired-cvs"


def aware(dt):
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def valid_csrf(request, token):
    expected = request.session.get("account_csrf", "")
    return bool(expected and token and hmac.compare_digest(expected, token))


def error_page(request, text, code=400):
    return templates.TemplateResponse(
        request=request, name="account_error.html", context={"message": text},
        status_code=code, headers={"Cache-Control": "no-store"},
    )


def private_draft(db, request, draft_id):
    account = current_account(db, request)
    if not account:
        return None, None
    draft = db.get(ApplicationDraft, draft_id)
    if not draft or draft.account_id != account.id:
        return account, None
    return account, draft


def good_docx(data):
    try:
        with ZipFile(BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist() and "[Content_Types].xml" in archive.namelist()
    except (BadZipFile, ValueError):
        return False


@router.post("/cuenta/borradores/{draft_id}/cv")
async def upload_cv(request: Request, draft_id: str, csrf_token: str = Form(""),
                    dummy_confirmed: bool = Form(False), cv: UploadFile | None = File(None)):
    if not valid_csrf(request, csrf_token):
        return error_page(request, "Sesión vencida. Recargá la página.", 403)
    if not dummy_confirmed:
        return error_page(request, "Solo se permiten CVs ficticios de prueba.")
    filename = (cv.filename or "").replace("\\", "/").split("/")[-1] if cv else ""
    ext = Path(filename).suffix.lower()
    try:
        content = await cv.read(MAX_CV + 1) if cv else b""
    finally:
        if cv:
            await cv.close()
    if not content or len(content) > MAX_CV or ext not in {".pdf", ".docx"}:
        return error_page(request, "Subí un PDF o DOCX ficticio de hasta 5 MB.")
    if (ext == ".pdf" and not content.startswith(b"%PDF-")) or (ext == ".docx" and not good_docx(content)):
        return error_page(request, "El archivo de prueba no tiene un formato válido.")
    mime = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with SessionLocal() as db:
        account, draft = private_draft(db, request, draft_id)
        if not account:
            return RedirectResponse("/cuenta", 303)
        if not draft:
            return error_page(request, "Borrador no encontrado.", 404)
        old = db.execute(select(DraftCV).where(DraftCV.draft_id == draft.id)).scalar_one_or_none()
        if old:
            return error_page(request, "Ya existe un CV de prueba. Eliminá el anterior antes de subir otro.")
        path = f"{account.id}/{draft.id}/{uuid4().hex}{ext}"
        try:
            upload_private(path, content, mime)
            db.add(DraftCV(
                draft_id=draft.id, storage_path=path,
                filename=filename[:160], size_bytes=len(content),
                expires_at=utc_now() + CV_LIFETIME,
            ))
            db.commit()
        except Exception:
            db.rollback()
            # Best-effort compensation; a scheduled cleanup is still required.
            try:
                remove_private(path)
            except CVStorageError:
                pass
            return error_page(request, "No se pudo guardar el CV. Revisá Storage y volvé a intentar.", 502)
    return RedirectResponse(f"/cuenta/borradores/{draft_id}", 303)


@router.post("/cuenta/borradores/{draft_id}/cv/eliminar")
def delete_cv(request: Request, draft_id: str, csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return error_page(request, "Sesión vencida.", 403)
    with SessionLocal() as db:
        account, draft = private_draft(db, request, draft_id)
        if not account:
            return RedirectResponse("/cuenta", 303)
        if not draft:
            return error_page(request, "Borrador no encontrado.", 404)
        attachment = db.execute(select(DraftCV).where(DraftCV.draft_id == draft.id)).scalar_one_or_none()
        if attachment:
            try:
                remove_private(attachment.storage_path)
            except CVStorageError:
                return error_page(request, "No pudimos eliminar el archivo. Intentá de nuevo.", 502)
            db.delete(attachment)
            db.commit()
    return RedirectResponse(f"/cuenta/borradores/{draft_id}", 303)


@router.post("/cuenta/borradores/{draft_id}/simular")
def start_simulation(request: Request, draft_id: str, csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return error_page(request, "Sesión vencida.", 403)
    with SessionLocal() as db:
        account, draft = private_draft(db, request, draft_id)
        if not account:
            return RedirectResponse("/cuenta", 303)
        if not draft:
            return error_page(request, "Borrador no encontrado.", 404)
        existing = db.execute(select(DraftSimulation).where(DraftSimulation.draft_id == draft.id)).scalar_one_or_none()
        if existing:
            return RedirectResponse(f"/cuenta/colas/{existing.id}", 303)
        cv = db.execute(select(DraftCV).where(DraftCV.draft_id == draft.id)).scalar_one_or_none()
        if not cv or aware(cv.expires_at) <= utc_now():
            return error_page(request, "Subí primero un CV ficticio que no haya vencido.")
        ids = list(dict.fromkeys(draft.business_ids))
        if not 1 <= len(ids) <= 10:
            return error_page(request, "El borrador debe contener entre 1 y 10 lugares.")
        businesses = db.execute(select(Business).where(Business.id.in_(ids), Business.active.is_(True))).scalars().all()
        names = {b.id: b.name for b in businesses}
        if len(names) != len(ids):
            return error_page(request, "Algunos negocios del borrador ya no están disponibles.")
        sim = DraftSimulation(draft_id=draft.id, account_id=account.id)
        db.add(sim)
        db.flush()
        for position, bid in enumerate(ids):
            db.add(DraftSimulationItem(simulation_id=sim.id, business_id=bid, business_name=names[bid], position=position))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.execute(select(DraftSimulation).where(DraftSimulation.draft_id == draft.id)).scalar_one()
            return RedirectResponse(f"/cuenta/colas/{existing.id}", 303)
        sim_id = sim.id
    return RedirectResponse(f"/cuenta/colas/{sim_id}", 303)


def private_sim(db, request, simulation_id):
    account = current_account(db, request)
    if not account:
        return None
    sim = db.get(DraftSimulation, simulation_id)
    return sim if sim and sim.account_id == account.id else None


def simulation_status(db, sim):
    items = db.execute(select(DraftSimulationItem).where(DraftSimulationItem.simulation_id == sim.id)
                       .order_by(DraftSimulationItem.position)).scalars().all()
    total = len(items)
    done = sum(i.status == "simulated" for i in items)
    return {"status": sim.status, "total": total, "done": done,
            "items": [{"name": i.business_name, "status": i.status} for i in items]}


@router.get("/cuenta/colas/{simulation_id}")
def simulation_page(request: Request, simulation_id: str):
    with SessionLocal() as db:
        sim = private_sim(db, request, simulation_id)
        if not sim:
            return error_page(request, "Simulación no encontrada o acceso no autorizado.", 404)
        if "account_csrf" not in request.session:
            request.session["account_csrf"] = secrets.token_urlsafe(32)
        return templates.TemplateResponse(request=request, name="account_simulation.html", context={
            "simulation_id": sim.id, "csrf_token": request.session["account_csrf"]
        }, headers={"Cache-Control": "no-store"})


@router.get("/cuenta/colas/{simulation_id}/estado")
def get_status(request: Request, simulation_id: str):
    with SessionLocal() as db:
        sim = private_sim(db, request, simulation_id)
        if not sim:
            return JSONResponse({"error": "No autorizado"}, status_code=404)
        return JSONResponse(simulation_status(db, sim), headers={"Cache-Control": "no-store"})


@router.post("/cuenta/colas/{simulation_id}/paso")
def simulate_one(request: Request, simulation_id: str, csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return JSONResponse({"error": "Solicitud inválida"}, status_code=403)
    with SessionLocal() as db:
        sim = private_sim(db, request, simulation_id)
        if not sim:
            return JSONResponse({"error": "No autorizado"}, status_code=404)
        # A row-level lock serializes two browser tabs advancing the same campaign.
        sim = db.execute(select(DraftSimulation).where(DraftSimulation.id == sim.id).with_for_update()).scalar_one()
        if sim.status != "completed":
            item = db.execute(select(DraftSimulationItem).where(
                DraftSimulationItem.simulation_id == sim.id,
                DraftSimulationItem.status == "queued",
            ).order_by(DraftSimulationItem.position).limit(1)).scalar_one_or_none()
            if item:
                item.status = "simulated"
                item.finished_at = utc_now()
                sim.status = "running"
                db.flush()
            remaining = db.execute(select(DraftSimulationItem.id).where(
                DraftSimulationItem.simulation_id == sim.id,
                DraftSimulationItem.status == "queued",
            ).limit(1)).first()
            if not remaining:
                sim.status = "completed"
                sim.finished_at = utc_now()
            db.commit()
        return JSONResponse(simulation_status(db, sim), headers={"Cache-Control": "no-store"})


def cleanup_expired(db):
    expired = db.execute(select(DraftCV).where(DraftCV.expires_at <= utc_now()).order_by(DraftCV.expires_at).limit(100)).scalars().all()
    removed = 0
    for cv in expired:
        try:
            remove_private(cv.storage_path)
        except CVStorageError:
            continue  # Keep database reference so cleanup can be retried.
        db.delete(cv)
        removed += 1
    db.commit()
    return removed


@router.post(MAINTENANCE_PATH)
def maintenance(request: Request, x_maintenance_token: str | None = Header(None)):
    key = os.environ.get("CV_CLEANUP_TOKEN", "")
    if len(key) < 32 or not x_maintenance_token or not hmac.compare_digest(key, x_maintenance_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    with SessionLocal() as db:
        return {"removed": cleanup_expired(db)}
