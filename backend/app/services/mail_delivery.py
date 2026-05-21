"""Orquesta envío Gmail OAuth, SMTP del usuario o SMTP global (.env)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.google_calendar_connection import GoogleCalendarConnection
from app.models.user_email_setting import UserEmailSetting
from app.services.email import send_email
from app.services.google_gmail import google_connection_can_send_mail
from app.services.user_smtp import get_user_smtp_config


def _google_connection(db: Session, acting_user_id: int) -> GoogleCalendarConnection | None:
    return (
        db.query(GoogleCalendarConnection)
        .filter(GoogleCalendarConnection.user_id == acting_user_id)
        .first()
    )


def user_can_send_mail(db: Session, acting_user_id: int) -> bool:
    """True si hay al menos un canal usable (Gmail OAuth, SMTP perfil o SMTP servidor)."""
    conn = _google_connection(db, acting_user_id)
    if conn and google_connection_can_send_mail(conn):
        return True
    if get_user_smtp_config(db, acting_user_id):
        return True
    if get_settings().smtp_host:
        return True
    return False


def send_mail_acting_as_user(
    db: Session,
    acting_user_id: int,
    to_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Preferencia (one-click Google primero):
    1) Gmail OAuth si la conexión tiene scope de envío
    2) SMTP configurado en Perfil
    3) Variables SMTP_* en .env del servidor

    Si SMTP del perfil falla y hay Gmail OAuth, se reintenta con Gmail.
    """
    conn = _google_connection(db, acting_user_id)
    gmail_ready = bool(conn and google_connection_can_send_mail(conn))

    if gmail_ready:
        r = send_email(
            db,
            to_email,
            subject,
            body,
            gmail_oauth_connection=conn,
        )
        if r.get('status') == 'sent':
            return {**r, 'via': 'gmail_oauth'}

    smtp_conf = get_user_smtp_config(db, acting_user_id)
    if smtp_conf:
        r = send_email(db, to_email, subject, body, smtp_config=smtp_conf)
        if r.get('status') == 'sent':
            return {**r, 'via': 'smtp_profile'}
        if gmail_ready and r.get('status') == 'error':
            retry = send_email(
                db,
                to_email,
                subject,
                body,
                gmail_oauth_connection=conn,
            )
            if retry.get('status') == 'sent':
                return {**retry, 'via': 'gmail_oauth'}
        return {**r, 'via': 'smtp_profile'}

    settings = get_settings()
    if settings.smtp_host:
        r = send_email(db, to_email, subject, body)
        return {**r, 'via': 'smtp_server'}

    return {**send_email(db, to_email, subject, body), 'via': None}
