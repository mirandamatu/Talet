from __future__ import annotations

from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.search import Search
from app.schemas.ai import (
    AICandidateFitOut,
    AIInterviewAnalysisIn,
    AIInterviewAnalysisOut,
    AISearchQuestionsOut,
)
from app.services.ai_engine import analyze_candidate_fit, analyze_interview, analyze_job_questions, extract_pdf_text
from app.services.ai_insights import create_ai_insight, get_candidate_fit_fields, get_search_questions_fields
from app.services.ai_notes import create_pinned_ai_note
from app.services.client_context import build_client_context
from app.services.notifications import create_event_notifications_for_roles
from app.services.user_clients import require_client_access

router = APIRouter(prefix='/ai', tags=['ai'])


def _candidate_cv_text(candidate: Candidate) -> str:
    if not candidate.cv_file_url:
        return ''
    if candidate.cv_file_url.startswith('/uploads/'):
        base_dir = Path(__file__).resolve().parents[2]
        full_path = base_dir / candidate.cv_file_url.lstrip('/')
        if full_path.exists():
            return extract_pdf_text(full_path.read_bytes())
        return ''
    if candidate.cv_file_url.startswith('http://') or candidate.cv_file_url.startswith('https://'):
        try:
            with urlopen(candidate.cv_file_url, timeout=15) as response:
                raw = response.read()
            return extract_pdf_text(raw)
        except (URLError, OSError, ValueError):
            return ''
    return ''


@router.get(
    '/candidates/{candidate_id}/fit',
    response_model=AICandidateFitOut,
    dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))],
)
def get_candidate_fit(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    fit = get_candidate_fit_fields(db, candidate.id)
    return {
        'candidate_id': candidate.id,
        'search_id': candidate.search_id,
        'score': fit.get('ai_fit_score'),
        'recommendation': fit.get('ai_fit_recommendation'),
        'summary': fit.get('ai_fit_summary'),
        'reasons': fit.get('ai_fit_reasons') or [],
        'model': None,
    }


@router.post(
    '/candidates/{candidate_id}/reanalyze',
    response_model=AICandidateFitOut,
    dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))],
)
def reanalyze_candidate_fit(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    fit = analyze_candidate_fit(
        search_title=search.title,
        job_description=search.job_description,
        candidate_name=candidate.full_name,
        short_profile=candidate.short_profile,
        cv_text=_candidate_cv_text(candidate),
    )
    create_ai_insight(
        db,
        entity_type='candidate',
        entity_id=candidate.id,
        kind='candidate_fit',
        score=fit.get('score'),
        recommendation=fit.get('recommendation'),
        summary=fit.get('summary'),
        payload_json={'reasons': fit.get('reasons') or [], 'model': fit.get('model') or 'heuristic'},
        created_by=user.id,
    )
    return {
        'candidate_id': candidate.id,
        'search_id': candidate.search_id,
        'score': fit.get('score'),
        'recommendation': fit.get('recommendation'),
        'summary': fit.get('summary'),
        'reasons': fit.get('reasons') or [],
        'model': fit.get('model'),
    }


@router.get(
    '/searches/{search_id}/questions',
    response_model=AISearchQuestionsOut,
    dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))],
)
def get_search_questions(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    data = get_search_questions_fields(db, search.id)
    return {
        'search_id': search.id,
        'needs_follow_up': data.get('ai_questions_needs_follow_up') or False,
        'summary': data.get('ai_questions_summary'),
        'questions': data.get('ai_questions') or [],
        'model': None,
    }


@router.post(
    '/searches/{search_id}/questions/reanalyze',
    response_model=AISearchQuestionsOut,
    dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))],
)
def reanalyze_search_questions(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    analysis = analyze_job_questions(title=search.title, job_description=search.job_description)
    create_ai_insight(
        db,
        entity_type='search',
        entity_id=search.id,
        kind='search_questions',
        score=None,
        recommendation=not analysis.get('needs_follow_up'),
        summary=analysis.get('summary'),
        payload_json={
            'needs_follow_up': bool(analysis.get('needs_follow_up')),
            'questions': analysis.get('questions') or [],
            'model': analysis.get('model') or 'heuristic',
        },
        created_by=user.id,
    )
    return {
        'search_id': search.id,
        'needs_follow_up': bool(analysis.get('needs_follow_up')),
        'summary': analysis.get('summary'),
        'questions': analysis.get('questions') or [],
        'model': analysis.get('model'),
    }


@router.post(
    '/interviews/{interview_id}/analyze',
    response_model=AIInterviewAnalysisOut,
    dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))],
)
def analyze_interview_route(
    interview_id: int,
    payload: AIInterviewAnalysisIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail='Interview not found')
    candidate = db.get(Candidate, interview.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)

    transcript = (payload.transcript or '').strip()
    if len(transcript) < 40:
        raise HTTPException(status_code=400, detail='Transcript is too short for AI analysis')

    analysis = analyze_interview(
        transcript=transcript,
        role_context=payload.role_context,
        search_title=search.title,
        job_description=search.job_description,
        candidate_name=candidate.full_name,
        short_profile=candidate.short_profile,
        client_context=build_client_context(db, search.client_id),
    )
    create_ai_insight(
        db,
        entity_type='interview',
        entity_id=interview.id,
        kind='interview_analysis',
        score=analysis.get('fit_score'),
        recommendation=analysis.get('recommendation'),
        summary=analysis.get('summary'),
        payload_json={
            'strengths': analysis.get('strengths') or [],
            'risks': analysis.get('risks') or [],
            'next_steps': analysis.get('next_steps') or [],
            'talent_feedback': analysis.get('talent_feedback') or '',
            'model': analysis.get('model') or 'heuristic',
        },
        created_by=user.id,
    )

    # Keep candidate-level AI fit synced with latest interview signal.
    create_ai_insight(
        db,
        entity_type='candidate',
        entity_id=candidate.id,
        kind='interview_fit',
        score=analysis.get('fit_score'),
        recommendation=analysis.get('recommendation'),
        summary=analysis.get('summary'),
        payload_json={
            'interview_id': interview.id,
            'strengths': analysis.get('strengths') or [],
            'risks': analysis.get('risks') or [],
            'next_steps': analysis.get('next_steps') or [],
            'model': analysis.get('model') or 'heuristic',
        },
        created_by=user.id,
    )

    create_pinned_ai_note(
        db,
        candidate_id=candidate.id,
        search_id=search.id,
        author_user_id=user.id,
        note_type="ai_interview_analysis",
        body=(
            f"Análisis IA entrevista — Score {analysis.get('fit_score')}/10\n"
            f"{analysis.get('summary') or ''}\n"
            f"Recomendación: {analysis.get('advance_recommendation') or analysis.get('talent_feedback') or ''}"
        )[:4000],
    )

    if payload.role_context == 'client_interview' or user.role == 'CLIENTE':
        create_event_notifications_for_roles(
            db,
            client_id=search.client_id,
            roles=['TALENT'],
            event_type='interview_ai_feedback_ready',
            title='Feedback IA de entrevista',
            message=f'Hay nueva devolucion IA para {candidate.full_name} en "{search.title}".',
            metadata={
                'interview_id': interview.id,
                'candidate_id': candidate.id,
                'candidate_name': candidate.full_name,
                'search_id': search.id,
                'search_title': search.title,
                'fit_score': analysis.get('fit_score'),
                'recommendation': analysis.get('recommendation'),
                'talent_feedback': analysis.get('talent_feedback'),
            },
        )

    return {
        'interview_id': interview.id,
        'candidate_id': candidate.id,
        'search_id': search.id,
        'fit_score': analysis.get('fit_score'),
        'recommendation': analysis.get('recommendation'),
        'summary': analysis.get('summary'),
        'strengths': analysis.get('strengths') or [],
        'risks': analysis.get('risks') or [],
        'next_steps': analysis.get('next_steps') or [],
        'talent_feedback': analysis.get('talent_feedback'),
        'model': analysis.get('model'),
    }
