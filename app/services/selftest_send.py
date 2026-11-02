"""Safe *single self-addressed* provider test: never accepts a recipient argument.

An HTTP 2xx means provider accepted the request, NOT recipient delivery.
"""
import base64
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import httpx

PDF = 'application/pdf'
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def sanitise_header(value: str) -> str:
    return ' '.join(value.replace('\r', ' ').replace('\n', ' ').split())[:180]


def build_self_message(account, draft, business_name: str, filename: str):
    subject = sanitise_header(draft.subject.replace('[Business Name]', business_name))
    subject = '[TEST - NO ENVIADO A EMPRESAS] ' + subject
    letter = (draft.cover_letter.replace('[Business Name]', business_name)
              .replace('[Your Name]', account.full_name))
    body = ('PRUEBA PERSONAL - NINGUNA EMPRESA RECIBIÓ ESTE EMAIL.\n'
            f'Empresa elegida para el ejemplo: {business_name}\n\n'
            f'Dear Hiring Manager,\n\n{letter}\n\nKind regards,\n'
            f'{account.full_name}\n{account.phone}\n')
    return subject, body


async def provider_self_send(connection, subject: str, body: str, filename: str, data: bytes):
    """Return HTTP status. A network error is an uncertain result (no retries)."""
    content_type = PDF if Path(filename).suffix.lower() == '.pdf' else DOCX
    recipient = connection.email  # From verified OAuth account; NEVER a business address.
    async with httpx.AsyncClient(timeout=30.0) as http:
        if connection.provider == 'google':
            message = EmailMessage()
            message['From'] = recipient
            message['To'] = recipient
            message['Subject'] = subject
            message.set_content(body)
            maintype, subtype = content_type.split('/', 1)
            message.add_attachment(data, maintype=maintype, subtype=subtype,
                                   filename=Path(filename).name)
            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
            res = await http.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                                  headers={'Authorization': 'Bearer ' + connection.access_token},
                                  json={'raw': encoded})
            return res.status_code
        if connection.provider == 'microsoft':
            if len(data) > 2_500_000:
                raise ValueError('Outlook: usá un CV de menos de 2,5 MB para esta prueba.')
            res = await http.post('https://graph.microsoft.com/v1.0/me/sendMail',
                                  headers={'Authorization': 'Bearer ' + connection.access_token},
                                  json={'message': {'subject': subject,
                                                    'body': {'contentType': 'Text', 'content': body},
                                                    'toRecipients': [{'emailAddress': {'address': recipient}}],
                                                    'attachments': [{'@odata.type': '#microsoft.graph.fileAttachment',
                                                                     'name': Path(filename).name,
                                                                     'contentType': content_type,
                                                                     'contentBytes': base64.b64encode(data).decode('ascii')} ]},
                                        'saveToSentItems': True})
            return res.status_code
        raise ValueError('Proveedor no disponible')
