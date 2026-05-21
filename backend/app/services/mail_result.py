"""Helpers compartidos para respuestas de envío de correo en rutas HTTP."""

from __future__ import annotations

from fastapi import HTTPException


def mail_result_or_raise(result: dict) -> dict:
    status = result.get('status')
    if status == 'sent':
        return result
    if status == 'skipped':
        raise HTTPException(
            status_code=400,
            detail=(
                'No hay manera de enviar correo: conectá Google desde Perfil (Continuar con Google), '
                'configurá SMTP manual en Perfil, o definí SMTP_HOST en .env del servidor.'
            ),
        )
    raise HTTPException(
        status_code=502,
        detail=str(result.get('message') or 'Error al enviar el correo.'),
    )
