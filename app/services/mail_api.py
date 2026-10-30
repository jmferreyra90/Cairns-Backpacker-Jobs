"""Send exactly one test email to the connected account, with a CV attachment."""
import base64
from email.message import EmailMessage

import httpx

from app.services.session_store import Connection, Draft


class SendError(Exception):
    pass


async def send_self_test(connection: Connection, draft: Draft, preview: dict) -> None:
    """Never send to the business here. Destination is the OAuth account itself."""
    recipient = connection.account_email
    subject = "[TEST ONLY] " + preview["subject"]
    body = (
        "TEST — no employer was contacted.\n"
        f"Original intended business: {preview['business_name']}\n\n"
        + preview["body"]
    )
    content_type = (
        "application/pdf" if draft.cv_filename.lower().endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if connection.provider == "google":
                msg = EmailMessage()
                msg["From"] = recipient
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.set_content(body)
                maintype, subtype = content_type.split("/", 1)
                msg.add_attachment(
                    draft.cv_bytes,
                    maintype=maintype,
                    subtype=subtype,
                    filename=draft.cv_filename,
                )
                encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
                response = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers={"Authorization": f"Bearer {connection.access_token}"},
                    json={"raw": encoded},
                )
                response.raise_for_status()

            elif connection.provider == "microsoft":
                # Small JSON attachments work for our local test. Larger files
                # will need Microsoft Graph's upload-session workflow.
                if len(draft.cv_bytes) > 2_500_000:
                    raise SendError(
                        "Para esta prueba de Outlook, elegí un CV de menos de 2,5 MB."
                    )
                response = await client.post(
                    "https://graph.microsoft.com/v1.0/me/sendMail",
                    headers={"Authorization": f"Bearer {connection.access_token}"},
                    json={
                        "message": {
                            "subject": subject,
                            "body": {"contentType": "Text", "content": body},
                            "toRecipients": [{"emailAddress": {"address": recipient}}],
                            "attachments": [{
                                "@odata.type": "#microsoft.graph.fileAttachment",
                                "name": draft.cv_filename,
                                "contentType": content_type,
                                "contentBytes": base64.b64encode(draft.cv_bytes).decode("ascii"),
                            }],
                        },
                        "saveToSentItems": True,
                    },
                )
                response.raise_for_status()
            else:
                raise SendError("Proveedor de email desconocido.")
    except httpx.HTTPStatusError as exc:
        # Do not expose provider responses/tokens in the webpage.
        if exc.response.status_code in (401, 403):
            raise SendError("No se pudo autorizar el envío. Volvé a conectar tu cuenta.") from exc
        raise SendError("El proveedor rechazó el envío de prueba.") from exc
    except httpx.RequestError as exc:
        raise SendError(
            "No pudimos confirmar el envío por un problema de red. "
            "Revisá Enviados antes de volver a intentar."
        ) from exc


class SendFailure(Exception):
    def __init__(self, message: str, *, uncertain: bool = False, stop: bool = True):
        super().__init__(message)
        self.uncertain = uncertain
        self.stop = stop


async def send_employer_application(connection: Connection, draft: Draft, preview: dict) -> None:
    """Send ONE vetted business email. Only called by confirmed, real-mode campaign.

    Successful response means ACCEPTED by provider, not guaranteed delivery.
    No automatic retries: ambiguous failures could duplicate an application.
    """
    recipient = preview["to"]
    content_type = (
        "application/pdf" if draft.cv_filename.lower().endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if connection.provider == "google":
                msg = EmailMessage()
                msg["From"] = connection.account_email
                msg["To"] = recipient
                msg["Subject"] = preview["subject"]
                msg.set_content(preview["body"])
                maintype, subtype = content_type.split("/", 1)
                msg.add_attachment(
                    draft.cv_bytes, maintype=maintype, subtype=subtype,
                    filename=draft.cv_filename,
                )
                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
                response = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers={"Authorization": f"Bearer {connection.access_token}"},
                    json={"raw": raw},
                )
            elif connection.provider == "microsoft":
                if len(draft.cv_bytes) > 2_500_000:
                    raise SendFailure("Outlook requiere un CV menor a 2,5 MB.")
                response = await client.post(
                    "https://graph.microsoft.com/v1.0/me/sendMail",
                    headers={"Authorization": f"Bearer {connection.access_token}"},
                    json={
                        "message": {
                            "subject": preview["subject"],
                            "body": {"contentType": "Text", "content": preview["body"]},
                            "toRecipients": [{"emailAddress": {"address": recipient}}],
                            "attachments": [{
                                "@odata.type": "#microsoft.graph.fileAttachment",
                                "name": draft.cv_filename,
                                "contentType": content_type,
                                "contentBytes": base64.b64encode(draft.cv_bytes).decode("ascii"),
                            }],
                        },
                        "saveToSentItems": True,
                    },
                )
            else:
                raise SendFailure("Proveedor desconocido.")
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 429:
            raise SendFailure("Límite del proveedor alcanzado. Detuvimos la cola.") from exc
        if code in (401, 403):
            raise SendFailure("Permiso vencido o envío rechazado. Reconectá tu cuenta.") from exc
        if code == 408 or 500 <= code <= 599:
            raise SendFailure(
                "Respuesta incierta del proveedor. Revisá Enviados antes de intentar otra vez.",
                uncertain=True,
            ) from exc
        raise SendFailure("El proveedor rechazó el envío. Revisá la configuración.") from exc
    except httpx.RequestError as exc:
        raise SendFailure(
            "No sabemos si el proveedor recibió la solicitud. Revisá Enviados antes de reintentar.",
            uncertain=True,
        ) from exc
