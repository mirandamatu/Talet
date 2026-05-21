from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from app.services.ai_agents import (
    candidate_fit_agent,
    interview_analysis_agent,
    regenerate_job_description_agent,
    search_questions_agent,
)


STOPWORDS = {
    'para', 'como', 'desde', 'hasta', 'entre', 'sobre', 'bajo', 'con', 'sin', 'por',
    'del', 'las', 'los', 'una', 'uno', 'unos', 'unas', 'que', 'esta', 'este', 'estos',
    'esas', 'esos', 'ser', 'estar', 'haber', 'perfil', 'busqueda', 'puesto', 'candidato',
}


def extract_pdf_text(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        return ''
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(BytesIO(pdf_bytes))
        chunks: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ''
            if text.strip():
                chunks.append(text.strip())
        return '\n'.join(chunks).strip()
    except Exception:
        # Last fallback for malformed files.
        return pdf_bytes.decode('utf-8', errors='ignore').strip()


def extract_docx_text(docx_bytes: bytes) -> str:
    if not docx_bytes:
        return ''
    try:
        from docx import Document  # type: ignore

        document = Document(BytesIO(docx_bytes))
        chunks = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return '\n'.join(chunks).strip()
    except Exception:
        return docx_bytes.decode('utf-8', errors='ignore').strip()


def extract_document_text(file_bytes: bytes, filename: str | None = None, content_type: str | None = None) -> str:
    name = (filename or '').lower()
    mime = (content_type or '').lower()
    if name.endswith('.docx') or 'wordprocessingml' in mime:
        return extract_docx_text(file_bytes)
    if name.endswith('.pdf') or mime == 'application/pdf':
        return extract_pdf_text(file_bytes)
    return file_bytes.decode('utf-8', errors='ignore').strip()


def _normalize_text(text: str) -> str:
    normalized = (text or '').lower()
    normalized = normalized.translate(str.maketrans('áéíóúüñ', 'aeiouun'))
    normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    return [t for t in normalized.split(' ') if len(t) > 2 and t not in STOPWORDS]


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'si'}
    return default


def _safe_score(value: Any, min_value: float = 0, max_value: float = 100) -> float:
    try:
        num = float(value)
    except Exception:
        num = min_value
    return max(min_value, min(max_value, num))


def _heuristic_candidate_fit(
    *,
    search_title: str,
    job_description: str,
    candidate_name: str,
    short_profile: str | None,
    cv_text: str | None,
) -> dict[str, Any]:
    search_tokens = _tokenize(f"{search_title} {job_description}")
    candidate_tokens = set(_tokenize(f"{candidate_name} {short_profile or ''} {cv_text or ''}"))
    overlap = sorted(set(token for token in search_tokens if token in candidate_tokens))
    overlap_ratio = (len(overlap) / len(search_tokens)) if search_tokens else 0
    score = int(min(98, max(10, round(overlap_ratio * 100))))
    recommendation = score >= 65
    status = 'RECOMENDADO' if recommendation else 'NO_RECOMENDADO'
    summary = (
        f"{status}: match estimado {score}%. "
        f"Coincidencias detectadas: {', '.join(overlap[:6]) if overlap else 'baja señal de match'}."
    )
    return {
        'score': score,
        'recommendation': recommendation,
        'summary': summary,
        'reasons': overlap[:8],
        'model': 'heuristic',
    }


def _score_to_ten(value: Any) -> float:
    numeric = _safe_score(value, 0, 100)
    if numeric <= 10:
        return round(numeric, 1)
    return round(numeric / 10, 1)


def analyze_candidate_fit(
    *,
    search_title: str,
    job_description: str,
    candidate_name: str,
    short_profile: str | None,
    cv_text: str | None,
    client_context: str | None = None,
) -> dict[str, Any]:
    heuristic = _heuristic_candidate_fit(
        search_title=search_title,
        job_description=job_description,
        candidate_name=candidate_name,
        short_profile=short_profile,
        cv_text=cv_text,
    )
    heuristic["score"] = round(heuristic["score"] / 10, 1)
    llm = candidate_fit_agent(
        search_title=search_title,
        job_description=job_description,
        candidate_name=candidate_name,
        short_profile=short_profile,
        cv_text=cv_text,
        client_context=client_context,
    )
    if not llm:
        return heuristic
    reasons = llm.get('reasons')
    if not isinstance(reasons, list):
        reasons = []
    score_10 = _score_to_ten(llm.get('score'))
    return {
        'score': score_10,
        'score_10': score_10,
        'recommendation': _safe_bool(llm.get('recommendation'), default=score_10 >= 7),
        'summary': str(llm.get('summary') or heuristic['summary'])[:500],
        'reasons': [str(item)[:120] for item in reasons[:10] if str(item).strip()],
        'strengths': [str(item)[:120] for item in (llm.get('strengths') or [])[:8]],
        'weaknesses': [str(item)[:120] for item in (llm.get('weaknesses') or [])[:8]],
        'model': 'llm',
    }


def _heuristic_search_questions(title: str, job_description: str) -> dict[str, Any]:
    text = _normalize_text(f"{title} {job_description}")
    questions: list[str] = []
    if not re.search(r'\b(remoto|hibrido|presencial|on site|remote|hybrid)\b', text):
        questions.append('Modalidad de trabajo: remoto, hibrido o presencial?')
    if not re.search(r'\b(salary|salario|compensacion|sueldo|remuneracion)\b', text):
        questions.append('Rango salarial esperado para esta busqueda?')
    if not re.search(r'\b(junior|semi senior|senior|sr|ssr|lead)\b', text):
        questions.append('Nivel de seniority requerido?')
    if not re.search(r'\b(ingles|english|bilingue)\b', text):
        questions.append('Nivel de ingles requerido para el rol?')
    if not re.search(r'\b(anos|anios|years|experiencia)\b', text):
        questions.append('Experiencia minima requerida en anos?')
    needs_follow_up = len(questions) > 0
    summary = 'Se detectaron vacios de informacion en la JD.' if needs_follow_up else 'La JD tiene contexto suficiente para iniciar.'
    return {
        'needs_follow_up': needs_follow_up,
        'summary': summary,
        'questions': questions[:8],
        'model': 'heuristic',
    }


def analyze_job_questions(*, title: str, job_description: str) -> dict[str, Any]:
    heuristic = _heuristic_search_questions(title, job_description)
    llm = search_questions_agent(title=title, job_description=job_description)
    if not llm:
        return heuristic
    questions = llm.get('questions')
    if not isinstance(questions, list):
        questions = []
    return {
        'needs_follow_up': _safe_bool(llm.get('needs_follow_up')),
        'summary': str(llm.get('summary') or heuristic['summary'])[:500],
        'questions': [str(item)[:180] for item in questions[:8] if str(item).strip()],
        'model': 'llm',
    }


def regenerate_job_description(*, title: str, job_description: str, answers: list[dict[str, str]]) -> str:
    clean_answers = [
        {'question': str(item.get('question') or '').strip(), 'answer': str(item.get('answer') or '').strip()}
        for item in answers
        if str(item.get('question') or '').strip() and str(item.get('answer') or '').strip()
    ]
    if not clean_answers:
        return job_description

    base_description = re.split(r'\n+Información complementaria respondida por el cliente/comercial:\n+', job_description or '', maxsplit=1)[0].strip()
    fallback_lines = [
        base_description,
        '',
        'Información complementaria respondida por el cliente/comercial:',
        *[f"- {item['question']} {item['answer']}" for item in clean_answers],
    ]
    fallback = '\n'.join(line for line in fallback_lines if line is not None).strip()
    llm = regenerate_job_description_agent(
        title=title,
        job_description=base_description,
        answers=clean_answers,
    )
    if not llm:
        return fallback
    next_description = str(llm.get('job_description') or '').strip()
    return next_description[:12000] if next_description else fallback


def _heuristic_interview_analysis(
    *,
    transcript: str,
    role_context: str,
    search_title: str,
    job_description: str,
    candidate_name: str,
    short_profile: str | None,
) -> dict[str, Any]:
    normalized = _normalize_text(transcript)
    positive_hits = len(re.findall(r'\b(excelente|fuerte|solido|bueno|lider|claro|proactivo)\b', normalized))
    risk_hits = len(re.findall(r'\b(duda|debil|falta|limitado|riesgo|brecha|baja)\b', normalized))
    base = 60 + (positive_hits * 6) - (risk_hits * 7)
    fit_score = int(max(5, min(98, base)))
    recommendation = fit_score >= 65
    strengths = []
    if positive_hits > 0:
        strengths.append('Menciona fortalezas tecnicas/comportamentales relevantes.')
    if fit_score >= 75:
        strengths.append('Consistencia general con la busqueda.')
    if not strengths:
        strengths.append('Sin fortalezas claras detectadas en la transcripcion.')
    risks = []
    if risk_hits > 0:
        risks.append('Se detectan senales de riesgo o brechas a validar.')
    if fit_score < 65:
        risks.append('Ajuste estimado por debajo del umbral recomendado.')
    if not risks:
        risks.append('Riesgo general bajo segun el contenido disponible.')
    next_steps = [
        'Validar ejemplos concretos de proyectos similares al rol.',
        'Corroborar stack tecnico requerido con ejercicios o referencias.',
    ]
    if role_context == 'client_interview':
        talent_feedback = 'Cliente entrevisto al candidato. Recomendar seguimiento con Talent y foco en brechas detectadas.'
    else:
        talent_feedback = 'Entrevista interna analizada. Continuar proceso si se mantiene el fit tecnico/cultural.'
    return {
        'fit_score': fit_score,
        'recommendation': recommendation,
        'summary': f'Analisis IA: ajuste estimado {fit_score}%.',
        'strengths': strengths[:4],
        'risks': risks[:4],
        'next_steps': next_steps[:4],
        'talent_feedback': talent_feedback,
        'model': 'heuristic',
    }


def analyze_interview(
    *,
    transcript: str,
    role_context: str,
    search_title: str,
    job_description: str,
    candidate_name: str,
    short_profile: str | None,
    client_context: str | None = None,
) -> dict[str, Any]:
    heuristic = _heuristic_interview_analysis(
        transcript=transcript,
        role_context=role_context,
        search_title=search_title,
        job_description=job_description,
        candidate_name=candidate_name,
        short_profile=short_profile,
    )
    heuristic["fit_score"] = round(heuristic["fit_score"] / 10, 1)
    llm = interview_analysis_agent(
        transcript=transcript,
        role_context=role_context,
        search_title=search_title,
        job_description=job_description,
        candidate_name=candidate_name,
        short_profile=short_profile,
        client_context=client_context,
    )
    if not llm:
        return heuristic
    fit_score = _score_to_ten(llm.get('fit_score'))
    return {
        'fit_score': fit_score,
        'score_10': fit_score,
        'recommendation': _safe_bool(llm.get('recommendation'), default=fit_score >= 7),
        'summary': str(llm.get('summary') or heuristic['summary'])[:700],
        'strengths': [str(item)[:220] for item in (llm.get('strengths') or [])[:5]],
        'risks': [str(item)[:220] for item in (llm.get('risks') or [])[:5]],
        'next_steps': [str(item)[:220] for item in (llm.get('next_steps') or [])[:5]],
        'talent_feedback': str(llm.get('talent_feedback') or heuristic['talent_feedback'])[:700],
        'advance_recommendation': str(llm.get('advance_recommendation') or '')[:400],
        'model': 'llm',
    }
