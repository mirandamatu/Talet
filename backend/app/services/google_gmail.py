"""Envío de correo mediante Gmail API (OAuth del usuario)."""

from __future__ import annotations

import base64

from email.message import EmailMessage
from googleapiclient.discovery import build

from app.models.google_calendar_connection import GoogleCalendarConnection
from app.services.google_calendar import connection_to_credentials


def google_connection_can_send_mail(connection: GoogleCalendarConnection | None) -> bool:
    if not connection or not connection.access_token:
        return False
    s = connection.scope or ''
    return (
        'gmail.send' in s
        or 'auth/gmail.compose' in s
        or 'https://mail.google.com/' in s
        or '/auth/gmail.modify' in s
    )


def send_gmail_text_email(
    connection: GoogleCalendarConnection,
    *,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    creds = connection_to_credentials(connection)
    if not creds:
        raise RuntimeError('No hay token de Google válido')
    from_addr = connection.google_email
    if not from_addr:
        raise RuntimeError('Falta el email de la cuenta Google conectada')
    msg = EmailMessage()
    msg['From'] = from_addr
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('ascii')
    svc = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    svc.users().messages().send(userId='me', body={'raw': raw}).execute()
