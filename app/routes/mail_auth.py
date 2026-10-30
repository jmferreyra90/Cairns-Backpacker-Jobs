"""OAuth redirect/callback. Connection tokens live in RAM, never in cookies."""
import time

import httpx
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database import SessionLocal
from app.services.contacts import save_applicant_contact
from app.services.oauth_clients import oauth
from app.services.session_store import Connection, get_draft, put_connection

router = APIRouter()


def message_page(message: str, status: int = 400):
    # Only predetermined/static strings passed here; no HTML from providers.
    return HTMLResponse(
        "<html lang='es'><meta charset='utf-8'>"
        f"<h2>{message}</h2><a href='/'>Volver al inicio</a></html>",
        status_code=status,
    )


@router.get("/connect/{provider}")
async def connect(provider: str, request: Request):
    if provider not in ("google", "microsoft"):
        return message_page("Proveedor no disponible.", 404)
    sid = request.session.get("sid")
    if not get_draft(sid):
        return message_page("La postulación venció. Volvé a completar el formulario.")
    client = oauth.create_client(provider)
    if not client:
        return message_page("Configurá primero las credenciales de este proveedor.")
    redirect_uri = request.url_for("oauth_callback", provider=provider)
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/auth/{provider}/callback", name="oauth_callback")
async def oauth_callback(provider: str, request: Request):
    if provider not in ("google", "microsoft"):
        return message_page("Proveedor no disponible.", 404)
    sid = request.session.get("sid")
    draft = get_draft(sid)
    if not draft:
        return message_page("La postulación venció. Volvé a completar el formulario.")
    client = oauth.create_client(provider)
    if not client:
        return message_page("Proveedor no configurado.")

    try:
        token = await client.authorize_access_token(request)  # Verifies OAuth state
        if provider == "google":
            claims = token.get("userinfo") or {}
            if claims.get("email_verified") is not True:
                return message_page("Google no confirmó la dirección de email.")
            account_email = str(claims.get("email", "")).strip().lower()
        else:
            async with httpx.AsyncClient(timeout=15.0) as http:
                me = await http.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token['access_token']}"},
                )
                me.raise_for_status()
                profile = me.json()
                account_email = str(
                    profile.get("mail") or profile.get("userPrincipalName") or ""
                ).strip().lower()
    except (OAuthError, httpx.HTTPError, KeyError, ValueError):
        return message_page("La conexión no se completó. Volvé a intentarlo.")

    if not account_email or account_email != draft.email:
        return message_page(
            "El email conectado debe coincidir con el que ingresaste "
            "en la postulación. Volvé al inicio y usá ese email."
        )

    # Only after provider identity verification do we persist marketing choices.
    with SessionLocal() as db:
        save_applicant_contact(
            db=db,
            full_name=draft.full_name,
            email=account_email,
            phone=draft.phone,
            marketing_opt_in=draft.marketing_opt_in,
            feedback_opt_in=draft.feedback_opt_in,
        )

    lifetime = min(float(token.get("expires_in", 3600)), 3600.0)
    put_connection(sid, Connection(
        provider=provider,
        account_email=account_email,
        access_token=token["access_token"],
        expires_at=time.time() + max(1.0, lifetime - 30.0),
    ))
    return RedirectResponse(url="/compose/ready", status_code=303)
