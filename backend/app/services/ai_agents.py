from __future__ import annotations

from typing import Any

from app.services.ai_client import chat_json


def candidate_fit_agent(
    *,
    search_title: str,
    job_description: str,
    candidate_name: str,
    short_profile: str | None,
    cv_text: str | None,
    client_context: str | None = None,
) -> dict[str, Any] | None:
    return chat_json(
        system_prompt=(
            "Sos un agente de recruiting especializado en evaluar fit entre candidatos y busquedas. "
            "Devolve JSON estricto con claves: score (1..10), recommendation (boolean), "
            "summary (string corta), reasons (array de strings cortos), strengths (array), weaknesses (array)."
        ),
        user_prompt=(
            f"Titulo de la busqueda:\n{search_title}\n\n"
            f"Descripcion del puesto:\n{job_description}\n\n"
            f"Contexto del cliente:\n{client_context or 'Sin contexto adicional.'}\n\n"
            f"Nombre del candidato:\n{candidate_name}\n\n"
            f"Resumen del perfil:\n{short_profile or ''}\n\n"
            f"Texto del CV:\n{(cv_text or '')[:12000]}"
        ),
    )


def matching_agent(
    *,
    search_title: str,
    job_description: str,
    client_context: str | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    compact = []
    for item in candidates[:40]:
        compact.append(
            {
                "candidate_id": item.get("candidate_id"),
                "name": item.get("name"),
                "profile": (item.get("profile") or "")[:1200],
                "cv_excerpt": (item.get("cv_excerpt") or "")[:2500],
            }
        )
    return chat_json(
        system_prompt=(
            "Sos un agente de matching de candidatos. Devolve JSON estricto con clave rankings: "
            "array de objetos {candidate_id, score (1..10), justification (string breve)} "
            "ordenado de mayor a menor score."
        ),
        user_prompt=(
            f"Busqueda: {search_title}\n\n"
            f"Job description:\n{job_description}\n\n"
            f"Contexto del cliente:\n{client_context or 'Sin contexto adicional.'}\n\n"
            f"Candidatos:\n{compact}"
        ),
    )


def search_questions_agent(*, title: str, job_description: str) -> dict[str, Any] | None:
    return chat_json(
        system_prompt=(
            "Sos un agente de recruiting que revisa job descriptions y detecta faltantes. "
            "Devolve JSON estricto con: needs_follow_up (boolean), summary (string), questions (array de strings)."
        ),
        user_prompt=(
            f"Titulo del puesto:\n{title}\n\n"
            f"Descripcion del puesto:\n{job_description}\n\n"
            "Devolve hasta 8 preguntas concretas y utiles."
        ),
    )


def regenerate_job_description_agent(
    *,
    title: str,
    job_description: str,
    answers: list[dict[str, str]],
) -> dict[str, Any] | None:
    return chat_json(
        system_prompt=(
            "Sos un agente de recruiting operations. Reescribi una job description completa, clara y profesional en espanol. "
            "Incorpora las respuestas adicionales. Devolve JSON estricto con la clave: job_description."
        ),
        user_prompt=(
            f"Titulo:\n{title}\n\n"
            f"Descripcion actual:\n{job_description}\n\n"
            f"Preguntas respondidas:\n{answers}"
        ),
    )


def interview_analysis_agent(
    *,
    transcript: str,
    role_context: str,
    search_title: str,
    job_description: str,
    candidate_name: str,
    short_profile: str | None,
    client_context: str | None = None,
) -> dict[str, Any] | None:
    return chat_json(
        system_prompt=(
            "Sos un agente especializado en analizar entrevistas laborales. "
            "Devolve JSON estricto con claves: fit_score (1..10), recommendation (boolean), summary (string), "
            "strengths (array), risks (array), next_steps (array), talent_feedback (string), "
            "advance_recommendation (string breve con avanzar o no avanzar)."
        ),
        user_prompt=(
            f"Contexto: {role_context}\n"
            f"Busqueda: {search_title}\n"
            f"Descripcion: {job_description}\n"
            f"Contexto del cliente:\n{client_context or 'Sin contexto adicional.'}\n"
            f"Candidato: {candidate_name}\n"
            f"Perfil resumido: {short_profile or ''}\n\n"
            f"Transcripcion:\n{transcript[:16000]}"
        ),
    )


def conversation_summary_agent(*, messages_text: str) -> dict[str, Any] | None:
    return chat_json(
        system_prompt=(
            "Sos un asistente que resume conversaciones de recruiting. "
            "Devolve JSON estricto con claves: summary (string), action_items (array de strings)."
        ),
        user_prompt=f"Conversacion:\n{messages_text[:16000]}",
    )
