"""Single-process local development queue. DO NOT run with multiple Uvicorn workers."""
import asyncio
import hashlib
import os
from datetime import datetime, timedelta, timezone
from time import time

from app.database import SessionLocal
from app.models import Business
from app.models_campaign import Campaign, CampaignAttempt, now_utc
from app.models_directory import BusinessContactReview
from app.services.business_recipients import approved_recipients
from app.services.email_builder import build_email_preview
from app.services.mail_api import SendFailure, send_employer_application
from app.services.session_store import clear, get_connection, get_draft

MAX_PER_CAMPAIGN = 500
SIMULATION_DELAY_SECONDS = 1
REAL_DELAY_SECONDS = 2
DUPLICATE_WINDOW_DAYS = 7


def owner_hash(sid: str) -> str:
    return hashlib.sha256(sid.encode("utf-8")).hexdigest()


def real_enabled() -> bool:
    return os.getenv("ENABLE_REAL_SEND", "false").strip().lower() == "true"


def recover_interrupted_campaigns() -> None:
    """At startup, mark abandoned attempts. Never retry automatically."""
    with SessionLocal() as db:
        active = db.query(Campaign).filter(Campaign.status.in_(["queued", "running", "cancelling"])).all()
        for campaign in active:
            campaign.status = "interrupted"
            campaign.finished_at = now_utc()
            pending = db.query(CampaignAttempt).filter(
                CampaignAttempt.campaign_id == campaign.id,
                CampaignAttempt.status.in_(["queued", "sending"]),
            )
            for attempt in pending:
                if attempt.status == "sending":
                    attempt.status = "uncertain"  # provider may have accepted before restart
                    attempt.note = "El servidor se reinició durante el envío; revisá Enviados."
                else:
                    attempt.status = "interrupted"
                    attempt.note = "No se intentó: servidor reiniciado."
                attempt.finished_at = now_utc()
        db.commit()


def preflight_real(db, draft, connection, businesses) -> str | None:
    """Checks before any outbound requests, avoiding duplicate/unverified contacts."""
    if not real_enabled():
        return "El envío real está deshabilitado en .env."
    if not connection or connection.account_email != draft.email or connection.expires_at <= time() + 60:
        return "Conectá nuevamente tu cuenta de email antes del envío."
    if connection.provider not in ("google", "microsoft"):
        return "Proveedor no permitido."
    if connection.provider == "microsoft" and len(draft.cv_bytes) > 2_500_000:
        return "Con Outlook, elegí un CV de menos de 2,5 MB."

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for business in businesses:
        review = db.get(BusinessContactReview, business.id)
        if not review or review.status != "approved":
            return f"{business.name}: contacto pendiente de aprobación para recibir postulaciones."
        recipients = approved_recipients(db, business)
        if not recipients:
            return f"{business.name}: no hay direcciones aprobadas para recibir postulaciones."
        verified = business.last_verified
        if not business.email_verified or verified is None or verified < cutoff.date():
            return f"{business.name}: verificá su email antes del envío real."

    # No application-specific daily quota. Provider limits, individual
    # approval, explicit consent and duplicate checks remain in force.

    # Recently contacted businesses will be SKIPPED at campaign creation,
    # rather than preventing the user from applying to every other business.
    return None


def recently_contacted_ids(db, sender_email: str, business_ids) -> set[int]:
    """One-week deduplication, including sends with uncertain provider outcomes."""
    ids = [int(x) for x in business_ids]
    if not ids:
        return set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=DUPLICATE_WINDOW_DAYS)
    rows = (
        db.query(CampaignAttempt.business_id)
        .join(Campaign, CampaignAttempt.campaign_id == Campaign.id)
        .filter(
            Campaign.sender_email == sender_email,
            Campaign.mode == "real",
            CampaignAttempt.attempted_at >= cutoff,
            CampaignAttempt.status.in_(("sending", "accepted", "uncertain")),
            CampaignAttempt.business_id.in_(ids),
        )
        .all()
    )
    return {r[0] for r in rows}


def _finish_remaining(db, campaign_id: str, status: str, note: str):
    pending = db.query(CampaignAttempt).filter(
        CampaignAttempt.campaign_id == campaign_id,
        CampaignAttempt.status == "queued",
    ).all()
    for row in pending:
        row.status = status
        row.note = note
        row.finished_at = now_utc()


async def run_campaign(campaign_id: str, sid: str) -> None:
    """Local background task: persist status for polling, no auto-retries."""
    try:
        with SessionLocal() as db:
            campaign = db.get(Campaign, campaign_id)
            if not campaign or campaign.status != "queued":
                return
            campaign.status = "running"
            db.commit()

        with SessionLocal() as db:
            attempts = db.query(CampaignAttempt).filter(
                CampaignAttempt.campaign_id == campaign_id,
                CampaignAttempt.status == "queued",
            ).order_by(CampaignAttempt.id).all()
            ids = [a.id for a in attempts]
            mode = db.get(Campaign, campaign_id).mode

        for position, attempt_id in enumerate(ids):
            with SessionLocal() as db:
                campaign = db.get(Campaign, campaign_id)
                if campaign and campaign.status == "cancelling":
                    _finish_remaining(db, campaign_id, "interrupted", "Cancelado antes del envío.")
                    campaign.status = "cancelled"
                    campaign.finished_at = now_utc()
                    db.commit()
                    return
            draft, connection = get_draft(sid), get_connection(sid)
            if not draft or (mode == "real" and (
                not connection or connection.account_email != draft.email or
                connection.expires_at <= time() + 30
            )):
                with SessionLocal() as db:
                    _finish_remaining(db, campaign_id, "interrupted", "La sesión venció o falta reconectar el email.")
                    db.get(Campaign, campaign_id).status = "interrupted"
                    db.get(Campaign, campaign_id).finished_at = now_utc()
                    db.commit()
                return

            with SessionLocal() as db:
                attempt = db.get(CampaignAttempt, attempt_id)
                business = db.get(Business, attempt.business_id)
                # Re-check unchanged recipient and admin approval immediately before each send.
                review = db.get(BusinessContactReview, attempt.business_id) if mode == "real" else None
                if (not business or not business.active or business.email != attempt.recipient_email or
                    (mode == "real" and (
                     not review or review.status != "approved" or
                     not business.email_verified or not business.last_verified or
                     business.last_verified < (datetime.now(timezone.utc) - timedelta(days=90)).date()))):
                    attempt.status = "failed"
                    attempt.note = "Destinatario cambió o ya no está verificado."
                    attempt.finished_at = now_utc()
                    db.commit()
                    continue
                preview = build_email_preview(
                    business, draft.full_name, draft.phone, draft.subject, draft.cover_letter
                )
                if mode == "real":
                    recipients = approved_recipients(db, business)
                    if not recipients or recipients[0] != attempt.recipient_email.lower():
                        attempt.status = "failed"
                        attempt.note = "Los contactos aprobados cambiaron antes del envío."
                        attempt.finished_at = now_utc()
                        db.commit()
                        continue
                    preview["to"] = ", ".join(recipients)
                attempt.status = "sending"
                attempt.attempted_at = now_utc()
                db.commit()

            failure = None
            if mode == "simulated":
                await asyncio.sleep(SIMULATION_DELAY_SECONDS)
            else:
                try:
                    await send_employer_application(connection, draft, preview)
                except SendFailure as exc:
                    failure = exc

            with SessionLocal() as db:
                attempt = db.get(CampaignAttempt, attempt_id)
                if failure:
                    attempt.status = "uncertain" if failure.uncertain else "failed"
                    attempt.note = str(failure)
                else:
                    attempt.status = "simulated" if mode == "simulated" else "accepted"
                    attempt.note = (
                        "Simulación: no se envió nada." if mode == "simulated"
                        else "Aceptado por el proveedor; entrega no confirmada."
                    )
                attempt.finished_at = now_utc()
                db.commit()

            if failure and failure.stop:
                with SessionLocal() as db:
                    _finish_remaining(db, campaign_id, "interrupted", "Cola detenida por error del proveedor.")
                    campaign = db.get(Campaign, campaign_id)
                    campaign.status = "stopped"
                    campaign.finished_at = now_utc()
                    db.commit()
                return
            if position < len(ids) - 1:
                await asyncio.sleep(SIMULATION_DELAY_SECONDS if mode == "simulated" else REAL_DELAY_SECONDS)

        with SessionLocal() as db:
            campaign = db.get(Campaign, campaign_id)
            campaign.status = "completed"
            campaign.finished_at = now_utc()
            db.commit()

    except Exception:
        # Never retry an uncertain provider request automatically.
        with SessionLocal() as db:
            campaign = db.get(Campaign, campaign_id)
            if campaign and campaign.status in ("queued", "running", "cancelling"):
                for row in db.query(CampaignAttempt).filter(
                    CampaignAttempt.campaign_id == campaign_id,
                    CampaignAttempt.status.in_(["sending", "queued"]),
                ):
                    if row.status == "sending":
                        row.status = "uncertain"
                        row.note = "Error inesperado durante el envío. Revisá Enviados."
                    else:
                        row.status = "interrupted"
                        row.note = "No se intentó por un error interno."
                    row.finished_at = now_utc()
                campaign.status = "stopped"
                campaign.finished_at = now_utc()
                db.commit()
    finally:
        clear(sid)
