"""Milestone 12: one explicitly confirmed self-addressed email per saved draft.

Only mounted in password-protected staging, with its own startup guard.
NO employer address is ever passed to the provider. No automatic retries.
"""
import hmac
import logging
import os
import time
from datetime import timezone

import httpx
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Business
from app.models_accounts import ApplicationDraft
from app.models_draft_ops import DraftCV
from app.models_selftest import SelfTestAttempt, utc_now
from app.services.account_auth import current_account
from app.services.oauth_clients import oauth
from app.services.private_cv import CVStorageError, download_private
from app.services.selftest_cache import SenderConnection, find, store, forget
from app.services.selftest_send import build_self_message, provider_self_send

log = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory='app/templates')
MAX_CV = 5 * 1024 * 1024


def page(request, status=200, **ctx):
    return templates.TemplateResponse(
        request=request, name='account_selftest.html',
        context={'csrf_token': request.session.get('account_csrf', ''), **ctx},
        status_code=status, headers={'Cache-Control': 'no-store'},
    )


def owner_and_draft(db, request, draft_id):
    account = current_account(db, request)
    if not account or account.email != os.environ['SELF_TEST_OWNER_EMAIL'].strip().lower():
        return None, None
    draft = db.get(ApplicationDraft, draft_id)
    if draft is None or draft.account_id != account.id:
        return account, None
    return account, draft


def valid_csrf(request, submitted):
    expected = request.session.get('account_csrf', '')
    return bool(expected and submitted and hmac.compare_digest(expected, submitted))


def aware(dt):
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def providers():
    return [name for name, cid in (
        ('google', 'GOOGLE_CLIENT_ID'), ('microsoft', 'MICROSOFT_CLIENT_ID')
    ) if os.getenv(cid) and os.getenv('GOOGLE_CLIENT_SECRET' if name == 'google' else 'MICROSOFT_CLIENT_SECRET')]


def draft_cv(db, account, draft):
    cv = db.execute(select(DraftCV).where(DraftCV.draft_id == draft.id)).scalar_one_or_none()
    if not cv or aware(cv.expires_at) <= utc_now():
        return None
    if cv.size_bytes <= 0 or cv.size_bytes > MAX_CV:
        return None
    if not cv.storage_path.startswith(f'{account.id}/{draft.id}/'):
        return None
    if not cv.filename.lower().endswith(('.pdf', '.docx')):
        return None
    return cv



@router.get('/cuenta/borradores/{draft_id}/prueba')
def selftest_home(request: Request, draft_id: str):
    with SessionLocal() as db:
        account, draft = owner_and_draft(db, request, draft_id)
        if not account:
            return RedirectResponse('/cuenta', status_code=303)
        if not draft:
            return page(request, status=404, error='Borrador no encontrado o cuenta no autorizada.', ready=False)
        cv = draft_cv(db, account, draft)
        attempt = db.execute(select(SelfTestAttempt).where(SelfTestAttempt.draft_id == draft.id)).scalar_one_or_none()
        connection = find(request, account.id, draft.id)
        business = db.get(Business, draft.business_ids[0]) if draft.business_ids else None
        if not business:
            return page(request, status=400, error='No hay un negocio válido en el borrador.', ready=False)
        subject, body = build_self_message(account, draft, business.name, cv.filename if cv else 'CV')
        return page(request, ready=bool(cv), draft_id=draft.id, email=account.email,
                    filename=cv.filename if cv else '', subject=subject, body=body,
                    provider=connection.provider if connection else '',
                    providers=providers(), attempt=attempt,
                    notice=request.query_params.get('notice', ''))


@router.get('/cuenta/borradores/{draft_id}/prueba/conectar/{provider}')
async def connect_provider(request: Request, draft_id: str, provider: str):
    if provider not in providers():
        return page(request, status=404, error='Proveedor no configurado.', ready=False)
    with SessionLocal() as db:
        account, draft = owner_and_draft(db, request, draft_id)
        if not account or not draft or not draft_cv(db, account, draft):
            return RedirectResponse('/cuenta', status_code=303)
        if db.execute(select(SelfTestAttempt).where(SelfTestAttempt.draft_id == draft.id)).scalar_one_or_none():
            return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba', status_code=303)
        request.session['m12_pending'] = {
            'account_id': account.id, 'draft_id': draft.id,
            'provider': provider, 'time': int(time.time()),
        }
    client = oauth.create_client(provider)
    callback_url = os.environ['APP_PUBLIC_URL'].rstrip('/') + f'/cuenta/prueba/callback/{provider}'
    return await client.authorize_redirect(request, callback_url)


@router.get('/cuenta/prueba/callback/{provider}')
async def provider_callback(request: Request, provider: str):
    pending = request.session.pop('m12_pending', None)
    if (not isinstance(pending, dict) or provider not in providers() or
        pending.get('provider') != provider or
        abs(time.time() - pending.get('time', 0)) > 600):
        return RedirectResponse('/cuenta?notice=conexion-vencida', status_code=303)
    draft_id = pending['draft_id']
    with SessionLocal() as db:
        account, draft = owner_and_draft(db, request, draft_id)
        if not account or not draft or pending.get('account_id') != account.id:
            return RedirectResponse('/cuenta', status_code=303)
        if db.execute(select(SelfTestAttempt).where(SelfTestAttempt.draft_id == draft.id)).scalar_one_or_none():
            return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba', status_code=303)
        own_email, own_id = account.email, account.id

    try:
        token = await oauth.create_client(provider).authorize_access_token(request)
        if provider == 'google':
            claims = token.get('userinfo') or {}
            if not claims.get('email'):
                async with httpx.AsyncClient(timeout=12) as client:
                    r = await client.get('https://openidconnect.googleapis.com/v1/userinfo',
                                         headers={'Authorization': 'Bearer ' + token['access_token']})
                    r.raise_for_status()
                    claims = r.json()
            linked_email = str(claims.get('email', '')).strip().lower()
            verified = claims.get('email_verified') is True
        else:
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.get('https://graph.microsoft.com/v1.0/me',
                                     headers={'Authorization': 'Bearer ' + token['access_token']})
                r.raise_for_status()
                profile = r.json()
            linked_email = str(profile.get('mail') or profile.get('userPrincipalName') or '').strip().lower()
            verified = bool(linked_email)
        if not verified or linked_email != own_email:
            return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba?notice=email-distinto', status_code=303)
        # Only access token retained; never keep refresh token or ID token.
        lifetime = max(1, min(float(token.get('expires_in', 600)) - 60, 600))
        store(request, SenderConnection(account_id=own_id, draft_id=draft_id, provider=provider,
                                        email=linked_email, access_token=token['access_token'],
                                        expires_at=time.time() + lifetime))
    except (OAuthError, httpx.HTTPError, KeyError, ValueError, TypeError):
        log.warning('M12 OAuth callback failed (no token or payload logged): provider=%s', provider)
        return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba?notice=conexion-fallida', status_code=303)
    return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba?notice=conectado', status_code=303)


@router.post('/cuenta/borradores/{draft_id}/prueba/enviar')
async def send_once(request: Request, draft_id: str, csrf_token: str = Form(''),
                    confirm_self_send: bool = Form(False)):
    if not valid_csrf(request, csrf_token) or not confirm_self_send:
        return page(request, status=403, error='Confirmá explícitamente el envío de prueba.', ready=False)
    with SessionLocal() as db:
        account, draft = owner_and_draft(db, request, draft_id)
        if not account or not draft:
            return page(request, status=404, error='No autorizado.', ready=False)
        connection = find(request, account.id, draft.id)
        if not connection or connection.email != account.email:
            return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba?notice=reconectar', status_code=303)
        cv = draft_cv(db, account, draft)
        if not cv:
            return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba?notice=cv-vencido', status_code=303)
        if db.execute(select(SelfTestAttempt).where(SelfTestAttempt.draft_id == draft.id)).scalar_one_or_none():
            return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba', status_code=303)
        business = db.get(Business, draft.business_ids[0]) if draft.business_ids else None
        if not business:
            return page(request, status=400, error='Negocio no disponible.', ready=False)
        subject, body = build_self_message(account, draft, business.name, cv.filename)
        path, filename, expected_size = cv.storage_path, cv.filename, cv.size_bytes
        provider, recipient = connection.provider, account.email
        account_id = account.id

    # Download before reserving a send attempt. Missing/invalid files don't use the one attempt.
    try:
        blob = await run_in_threadpool(download_private, path)
        if not (0 < len(blob) <= MAX_CV) or len(blob) != expected_size:
            return page(request, status=422, error='El CV no coincide con el archivo guardado.', ready=False)
        if filename.lower().endswith('.pdf') and not blob.startswith(b'%PDF-'):
            return page(request, status=422, error='El PDF guardado no es válido.', ready=False)
        if connection.provider == 'microsoft' and len(blob) > 2_500_000:
            return page(request, status=422, error='Para Outlook, usá un CV menor a 2,5 MB.', ready=False)
    except CVStorageError:
        return page(request, status=502, error='No se pudo recuperar el CV privado.', ready=False)

    # Durable unique constraint: no replay on duplicate clicks, worker crash, network ambiguity.
    with SessionLocal() as db:
        account, draft = owner_and_draft(db, request, draft_id)
        if not account or not draft:
            return page(request, status=404, error='No autorizado.', ready=False)
        if not draft_cv(db, account, draft):
            return page(request, status=410, error='El CV venció antes de enviarlo.', ready=False)
        attempt = SelfTestAttempt(draft_id=draft_id, account_id=account_id,
                                  provider=provider, recipient_email=recipient,
                                  status='reserved')
        db.add(attempt)
        try:
            db.commit()
            attempt_id = attempt.id
        except IntegrityError:
            db.rollback()
            return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba', status_code=303)

    # Connection is single-use. Any error after reservation requires inspecting Sent.
    forget(request)
    status = 'uncertain'
    code = None
    try:
        code = await provider_self_send(connection, subject, body, filename, blob)
        if (provider == 'google' and code == 200) or (provider == 'microsoft' and code == 202):
            status = 'accepted'
        elif 400 <= code < 500 and code != 429:
            status = 'rejected'
    except Exception as exc:
        # Do not log tokens, email bodies or filenames.
        log.warning('M12 provider call uncertain: %s', type(exc).__name__)
    finally:
        with SessionLocal() as db:
            attempt = db.get(SelfTestAttempt, attempt_id)
            if attempt:
                attempt.status = status
                attempt.provider_http_status = code
                attempt.finished_at = utc_now()
                db.commit()
    return RedirectResponse(f'/cuenta/borradores/{draft_id}/prueba', status_code=303)
