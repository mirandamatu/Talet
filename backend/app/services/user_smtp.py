"""Credenciales SMTP opcionales por usuario (panel Perfil → correo)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user_email_setting import UserEmailSetting


def get_user_smtp_config(db: Session, user_id: int) -> dict | None:
    """Dict compatible con send_email(.., smtp_config=) o None si no hay cuenta configurada."""
    setting = db.query(UserEmailSetting).filter(UserEmailSetting.user_id == user_id).first()
    if not setting or not setting.is_configured:
        return None
    return {
        'smtp_host': setting.smtp_host,
        'smtp_port': setting.smtp_port,
        'smtp_user': setting.smtp_user,
        'smtp_password': setting.smtp_password,
        'smtp_from_email': setting.smtp_from_email,
        'use_tls': setting.use_tls,
    }
