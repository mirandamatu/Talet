from __future__ import annotations

from app.services.ai_client import chat_json


def generate_mail_draft(
    *,
    kind: str,
    candidate_name: str,
    search_title: str | None,
    search_description: str | None,
    extra_context: str | None = None,
    reason: str | None = None,
    interested_url: str | None = None,
    not_interested_url: str | None = None,
) -> dict[str, str]:
    fallback_subjects = {
        "contact": f"Oportunidad laboral: {search_title or 'Nueva busqueda'}",
        "discard": f"Actualizacion sobre tu postulacion a {search_title or 'la busqueda'}",
        "advance": f"Avance en el proceso - {search_title or 'Busqueda'}",
        "interview_invite": f"Coordinacion de entrevista - {search_title or 'Busqueda'}",
    }
    fallback_body = {
        "contact": (
            f"Hola {candidate_name},\n\n"
            f"Tenemos una busqueda abierta para {search_title or 'un nuevo rol'}.\n"
            "Queremos saber si te interesa avanzar en el proceso.\n\n"
            f"Estoy interesado: {interested_url or ''}\n"
            f"No estoy interesado: {not_interested_url or ''}\n\n"
            "Saludos,\nEquipo Atipia"
        ),
        "discard": (
            f"Hola {candidate_name},\n\n"
            f"Queremos agradecerte por tu tiempo en el proceso para {search_title or 'esta posicion'}.\n"
            f"En esta oportunidad no vamos a continuar. Motivo general: {reason or 'avanzamos con un perfil mas alineado al momento actual del proceso'}.\n\n"
            "Te agradecemos mucho el interes y esperamos volver a cruzarnos.\n\n"
            "Saludos,\nEquipo Atipia"
        ),
        "advance": (
            f"Hola {candidate_name},\n\n"
            f"Queremos contarte que avanzaste en el proceso para {search_title or 'esta busqueda'}.\n"
            "En breve te compartiremos los proximos pasos.\n\n"
            "Saludos,\nEquipo Atipia"
        ),
        "interview_invite": (
            f"Hola {candidate_name},\n\n"
            f"Queremos invitarte a coordinar una entrevista para {search_title or 'esta busqueda'}.\n"
            "Te compartiremos opciones de horario para que elijas la que mejor te quede.\n\n"
            "Saludos,\nEquipo Atipia"
        ),
    }
    llm = chat_json(
        system_prompt=(
            "Sos un agente redactor de emails de recruiting. "
            "Escribi en espanol, tono profesional y calido. "
            "Devolve JSON estricto con subject y body."
        ),
        user_prompt=(
            f"Tipo de mail: {kind}\n"
            f"Candidato: {candidate_name}\n"
            f"Busqueda: {search_title or ''}\n"
            f"Descripcion de la busqueda: {(search_description or '')[:5000]}\n"
            f"Motivo: {reason or ''}\n"
            f"Contexto extra: {extra_context or ''}\n"
            f"URL interesado: {interested_url or ''}\n"
            f"URL no interesado: {not_interested_url or ''}\n"
        ),
        temperature=0.35,
    )
    subject = str((llm or {}).get("subject") or fallback_subjects.get(kind) or "Actualizacion de recruiting").strip()
    body = str((llm or {}).get("body") or fallback_body.get(kind) or "").strip()
    return {"subject": subject[:255], "body": body[:12000]}
