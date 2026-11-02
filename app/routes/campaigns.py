"""Campaign start + read-only status. Explicitly gated employer sending."""
import hmac

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models_campaign import Campaign, CampaignAttempt
from app.services.campaign_queue import (
    MAX_PER_CAMPAIGN, owner_hash, preflight_real, real_enabled, run_campaign,
    recently_contacted_ids,
)
from app.services.session_store import get_connection, get_draft
from app.routes.applications import get_selected_businesses

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_owned(db, request, campaign_id):
    sid = request.session.get("sid")
    if not sid:
        raise HTTPException(status_code=404, detail="No se encontró la campaña.")
    campaign = db.get(Campaign, campaign_id)
    if not campaign or not hmac.compare_digest(campaign.session_hash, owner_hash(sid)):
        raise HTTPException(status_code=404, detail="No se encontró la campaña.")
    return campaign


@router.post("/campaigns/start")
async def start_campaign(
    request: Request,
    background_tasks: BackgroundTasks,
    csrf_token: str = Form(""),
    mode: str = Form("simulated"),
    confirm_real: bool = Form(False),
):
    sid = request.session.get("sid")
    expected = request.session.get("csrf", "")
    if not sid or not expected or not hmac.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=403, detail="Sesión inválida.")
    if mode not in ("simulated", "real"):
        raise HTTPException(status_code=400, detail="Modo no válido.")

    draft = get_draft(sid)
    if not draft:
        raise HTTPException(status_code=410, detail="La postulación venció. Volvé al inicio.")
    if draft.campaign_id:
        return RedirectResponse(url=f"/campaigns/{draft.campaign_id}", status_code=303)

    businesses = get_selected_businesses(",".join(str(i) for i in draft.business_ids))
    if len(businesses) != len(draft.business_ids) or len(businesses) > MAX_PER_CAMPAIGN:
        raise HTTPException(
            status_code=400,
            detail=f"Elegí de 1 a {MAX_PER_CAMPAIGN} negocios con email para esta campaña.",
        )

    connection = get_connection(sid)
    if mode == "real" and not confirm_real:
        raise HTTPException(status_code=400, detail="Confirmá explícitamente el envío real.")

    with SessionLocal() as db:
        if mode == "real":
            problem = preflight_real(db, draft, connection, businesses)
            if problem:
                raise HTTPException(status_code=400, detail=problem)

        skipped_ids = recently_contacted_ids(db, draft.email, [b.id for b in businesses]) if mode == "real" else set()
        campaign = Campaign(
            session_hash=owner_hash(sid), sender_email=draft.email,
            provider=connection.provider if connection else "none",
            mode=mode, status="queued",
        )
        db.add(campaign)
        db.flush()
        for business in businesses:
            db.add(CampaignAttempt(
                campaign_id=campaign.id,
                business_id=business.id,
                business_name=business.name,
                recipient_email=business.email,
                status="skipped" if business.id in skipped_ids else "queued",
                note=("Omitido: intento aceptado o incierto durante los últimos 7 días."
                      if business.id in skipped_ids else None),
            ))
        db.commit()
        campaign_id = campaign.id

    draft.campaign_id = campaign_id
    background_tasks.add_task(run_campaign, campaign_id, sid)
    return RedirectResponse(url=f"/campaigns/{campaign_id}", status_code=303)


@router.get("/campaigns/{campaign_id}")
def campaign_page(request: Request, campaign_id: str):
    with SessionLocal() as db:
        campaign = _get_owned(db, request, campaign_id)
        return templates.TemplateResponse(
            request=request,
            name="campaign_progress.html",
            context={"campaign_id": campaign.id, "mode": campaign.mode,
                     "csrf_token": request.session.get("csrf", "")},
            headers={"Cache-Control": "no-store"},
        )


@router.get("/campaigns/{campaign_id}/status")
def campaign_status(request: Request, campaign_id: str):
    with SessionLocal() as db:
        campaign = _get_owned(db, request, campaign_id)
        attempts = db.query(CampaignAttempt).filter(
            CampaignAttempt.campaign_id == campaign.id,
        ).order_by(CampaignAttempt.id).all()
        data = {
            "mode": campaign.mode,
            "status": campaign.status,
            "total": len(attempts),
            "processed": sum(a.status not in ("queued", "sending") for a in attempts),
            "accepted": sum(a.status == "accepted" for a in attempts),
            "simulated": sum(a.status == "simulated" for a in attempts),
            "failed": sum(a.status == "failed" for a in attempts),
            "uncertain": sum(a.status == "uncertain" for a in attempts),
            "skipped": sum(a.status == "skipped" for a in attempts),
            "attempts": [
                {
                    "business": a.business_name,
                    "recipient": a.recipient_email,
                    "status": a.status,
                    "note": a.note or "",
                }
                for a in attempts
            ],
        }
        return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.post("/campaigns/{campaign_id}/cancel")
def cancel_campaign(request: Request, campaign_id: str, csrf_token: str = Form("")):
    expected = request.session.get("csrf", "")
    if not expected or not hmac.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=403, detail="Sesión inválida.")
    with SessionLocal() as db:
        campaign = _get_owned(db, request, campaign_id)
        if campaign.status in ("queued", "running"):
            campaign.status = "cancelling"
            db.commit()
    return RedirectResponse(url=f"/campaigns/{campaign_id}", status_code=303)


@router.get("/mis-postulaciones")
def my_campaigns(request: Request):
    sid = request.session.get("sid")
    if not sid:
        campaigns = []
    else:
        with SessionLocal() as db:
            rows = db.query(Campaign).filter(
                Campaign.session_hash == owner_hash(sid)
            ).order_by(Campaign.created_at.desc()).limit(30).all()
            campaigns = [
                dict(id=c.id, mode=c.mode, status=c.status, created_at=c.created_at)
                for c in rows
            ]
    return templates.TemplateResponse(
        request=request, name="campaign_history.html",
        context={"campaigns": campaigns}, headers={"Cache-Control": "no-store"},
    )
