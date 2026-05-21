import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.google_calendar_connection import GoogleCalendarConnection
from app.models.notification_log import NotificationLog


def send_email(
    db: Session,
    to_email: str,
    subject: str,
    body: str,
    smtp_config: dict | None = None,
    *,
    gmail_oauth_connection: GoogleCalendarConnection | None = None,
) -> dict:
    settings = get_settings()
    log = NotificationLog(type='email', to_email=to_email, status='pending', retries=0)
    db.add(log)
    db.commit()

    if gmail_oauth_connection is not None:
        try:
            from app.services.google_gmail import send_gmail_text_email

            send_gmail_text_email(
                gmail_oauth_connection,
                to_email=to_email,
                subject=subject,
                body=body,
            )
            log.status = 'sent'
            db.commit()
            return {'status': 'sent', 'message': 'Correo enviado via Gmail'}
        except Exception as exc:
            log.status = 'error'
            log.retries += 1
            log.error = str(exc)
            db.commit()
            return {'status': 'error', 'message': str(exc)}

    config = smtp_config or {}
    smtp_host = config.get('smtp_host') or settings.smtp_host
    smtp_port = int(config.get('smtp_port') or settings.smtp_port)
    smtp_user = config.get('smtp_user') or settings.smtp_user
    smtp_password = config.get('smtp_password') or settings.smtp_password
    smtp_from_email = config.get('smtp_from_email') or settings.smtp_from_email
    use_tls = config.get('use_tls')
    if use_tls is None:
        use_tls = True

    if not smtp_host:
        log.status = 'skipped'
        log.error = 'SMTP not configured'
        db.commit()
        return {'status': 'skipped', 'message': 'SMTP no configurado (ni Gmail OAuth): Perfil SMTP, conectar Google, o SMTP_* en .env'}

    msg = EmailMessage()
    msg['From'] = smtp_from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        log.status = 'sent'
        db.commit()
        return {'status': 'sent', 'message': 'Correo enviado por SMTP'}
    except Exception as exc:
        log.status = 'error'
        log.retries += 1
        log.error = str(exc)
        db.commit()
        return {'status': 'error', 'message': str(exc)}
