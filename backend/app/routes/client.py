import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.availability_slot import AvailabilitySlot
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.feedback import Feedback
from app.models.interview import Interview
from app.models.notification_log import NotificationLog
from app.models.search import Search
from app.models.search_ai_question import SearchAIQuestion
from app.models.search_document import SearchDocument
from app.models.status_history import StatusHistory
from app.models.user import User
from app.schemas.candidate import CandidateAssignmentCreate, CandidateBankOut, CandidateOut, CandidateStatusUpdate, CandidateUpdate
from app.schemas.client import ClientOut
from app.schemas.feedback import FeedbackCreate
from app.schemas.interview import InterviewCreate, InterviewOut
from app.schemas.search import SearchOut
from app.services.ai_insights import get_candidate_fit_fields, get_search_questions_fields
from app.services.metrics import build_metrics_summary
from app.services.notifications import (
    archive_notifications,
    create_event_notifications_for_roles,
    list_event_notifications_for_user,
    mark_notifications_read,
    mark_notifications_read_by_ids,
    notify_user,
    notify_users,
)
from app.services.presentations import get_presentation, is_presented_to_client, resolve_assigned_talent
from app.services.search_states import classify_search, get_search_candidate_counts
from app.services.tenancy import ensure_candidate_in_organization, require_organization_id
from app.services.user_clients import can_access_client, get_accessible_clients, get_user_client_ids
from app.services.candidate_assignments import (
    assign_candidate_to_search,
    get_assignment,
    list_assignments_for_candidate,
    list_candidates_for_search,
    serialize_assignment,
    sync_assignment_status,
)

router = APIRouter(tags=['client'])


class InternalNotesUpdate(BaseModel):
    internal_notes: str | None = None


class NotificationArchivePayload(BaseModel):
    ids: list[int]


class NotificationReadPayload(BaseModel):
    ids: list[int]


class InterviewCancelPayload(BaseModel):
    reason: str | None = None


def _resolve_candidate_search_id(candidate: Candidate, db: Session, search_id: int | None = None) -> int | None:
    if search_id is not None:
        return search_id
    if candidate.search_id is not None:
        return candidate.search_id
    assignment = list_assignments_for_candidate(db, candidate.id)
    return assignment[0].search_id if assignment else None


def _serialize_candidate(
    candidate: Candidate,
    db: Session,
    include_internal: bool = False,
    viewer_role: str | None = None,
    search_id: int | None = None,
) -> dict:
    context_search_id = _resolve_candidate_search_id(candidate, db, search_id)
    assignment = get_assignment(db, candidate.id, context_search_id) if context_search_id is not None else None
    feedback_rows = (
        db.query(Feedback)
        .filter(Feedback.candidate_id == candidate.id)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .all()
    )
    latest_feedback = feedback_rows[0] if feedback_rows else None
    discarded_reason = latest_feedback.main_reason if latest_feedback else None
    discarded_comment = latest_feedback.comment if latest_feedback else None
    client_feedback = [
        {
            'id': row.id,
            'candidate_id': row.candidate_id,
            'search_id': context_search_id,
            'created_by_user_id': row.created_by,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'main_reason': row.main_reason,
            'rating_technical': (row.ratings_json or {}).get('tecnica') if row.ratings_json else None,
            'rating_communication': (row.ratings_json or {}).get('comunicacion') if row.ratings_json else None,
            'rating_cultural': (row.ratings_json or {}).get('cultural') if row.ratings_json else None,
            'comment': row.comment,
            'context': 'REJECTED',
        }
        for row in feedback_rows
    ]

    ai_fit = get_candidate_fit_fields(db, candidate.id)
    presented = context_search_id is not None and is_presented_to_client(db, candidate.id, context_search_id)
    presentation = get_presentation(db, candidate.id, context_search_id) if context_search_id is not None else None
    hide_cv = viewer_role == 'CLIENTE' and not presented
    assignments = list_assignments_for_candidate(db, candidate.id)

    return {
        'id': candidate.id,
        'search_id': context_search_id,
        'full_name': candidate.full_name,
        'email': candidate.email,
        'short_profile': candidate.short_profile,
        'cv_file_url': None if hide_cv else candidate.cv_file_url,
        'cv_file_name': None if hide_cv else candidate.cv_file_name,
        'cv_uploaded_at': candidate.cv_uploaded_at.isoformat() if candidate.cv_uploaded_at and not hide_cv else None,
        'status': candidate.status,
        'source': candidate.source,
        'archived_at': candidate.archived_at.isoformat() if candidate.archived_at else None,
        'discarded_reason': discarded_reason,
        'discarded_comment': discarded_comment,
        'internal_notes': candidate.internal_notes if include_internal else None,
        'has_client_feedback': len(client_feedback) > 0,
        'latest_client_feedback_reason': latest_feedback.main_reason if latest_feedback else None,
        'client_feedback': client_feedback,
        'is_presented_to_client': presented,
        'presented_at': presentation.presented_at.isoformat() if presentation else None,
        'assignment_status': assignment.status if assignment else candidate.status,
        'assignments': [serialize_assignment(row) for row in assignments],
        **ai_fit,
    }


def _serialize_search(search: Search, db: Session) -> dict:
    documents = (
        db.query(SearchDocument)
        .filter(SearchDocument.search_id == search.id)
        .order_by(SearchDocument.id.desc())
        .all()
    )
    question_rows = (
        db.query(SearchAIQuestion)
        .filter(SearchAIQuestion.search_id == search.id)
        .order_by(SearchAIQuestion.id)
        .all()
    )
    counts = get_search_candidate_counts(db, search.id)
    return {
        'id': search.id,
        'client_id': search.client_id,
        'title': search.title,
        'job_description': search.job_description,
        'contact_name': search.contact_name,
        'contact_email': search.contact_email,
        'archived_at': search.archived_at.isoformat() if search.archived_at else None,
        'search_state': classify_search(search, db),
        'manual_state': search.manual_state,
        'assigned_talent_user_id': search.assigned_talent_user_id,
        'alert_stale_days': search.alert_stale_days,
        'alert_no_response_days': search.alert_no_response_days,
        'deactivated_at': search.deactivated_at.isoformat() if search.deactivated_at else None,
        'candidate_count': counts['candidate_count'],
        'active_candidate_count': counts['active_candidate_count'],
        'documents': [
            {
                'id': row.id,
                'search_id': row.search_id,
                'kind': row.kind,
                'file_name': row.file_name,
                'file_url': row.file_url,
                'content_type': row.content_type,
                'extracted_text': row.extracted_text,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in documents
        ],
        'ai_question_items': [
            {
                'id': row.id,
                'search_id': row.search_id,
                'question': row.question,
                'answer': row.answer,
                'status': row.status,
            }
            for row in question_rows
        ],
        **get_search_questions_fields(db, search.id),
    }


def _is_hidden_for_client(user, candidate: Candidate, db: Session, search_id: int | None = None) -> bool:
    if user.role != 'CLIENTE':
        return candidate.archived_at is not None
    if candidate.archived_at is not None:
        return True
    context_search_id = _resolve_candidate_search_id(candidate, db, search_id)
    return context_search_id is None or not is_presented_to_client(db, candidate.id, context_search_id)


def _get_latest_cancel_reason(db: Session, interview_id: int) -> str | None:
    match = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.type == 'event',
            NotificationLog.error.isnot(None),
            NotificationLog.error.contains('"event_type": "interview_cancelled_by_client"'),
            NotificationLog.error.contains(f'"interview_id": {interview_id}'),
        )
        .order_by(NotificationLog.id.desc())
        .first()
    )
    if not match or not match.error:
        return None
    try:
        payload = json.loads(match.error)
        return (payload.get('metadata') or {}).get('reason')
    except Exception:
        return None


@router.get('/my/clients', response_model=list[ClientOut], dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def my_clients(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return get_accessible_clients(user, db)


@router.get('/notifications', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_notifications(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return list_event_notifications_for_user(db, user.email)


@router.post('/notifications/read-all', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def read_all_notifications(user=Depends(get_current_user), db: Session = Depends(get_db)):
    updated = mark_notifications_read(db, user.email)
    return {'status': 'ok', 'updated': updated}


@router.post('/notifications/read', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def read_notifications_by_ids(payload: NotificationReadPayload, user=Depends(get_current_user), db: Session = Depends(get_db)):
    updated = mark_notifications_read_by_ids(db, user.email, payload.ids)
    return {'status': 'ok', 'updated': updated}


@router.post('/notifications/archive', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def archive_user_notifications(payload: NotificationArchivePayload, user=Depends(get_current_user), db: Session = Depends(get_db)):
    updated = archive_notifications(db, user.email, payload.ids)
    return {'status': 'ok', 'updated': updated}


@router.get('/my/searches', response_model=list[SearchOut], dependencies=[Depends(require_roles('CLIENTE'))])
def my_searches(user=Depends(get_current_user), db: Session = Depends(get_db)):
    client_ids = get_user_client_ids(user)
    if not client_ids or user.organization_id is None:
        return []
    searches = (
        db.query(Search)
        .join(Client, Search.client_id == Client.id)
        .filter(
            Search.client_id.in_(client_ids),
            Client.organization_id == user.organization_id,
            Search.archived_at.is_(None),
        )
        .order_by(Search.id)
        .all()
    )
    return [_serialize_search(search, db) for search in searches]


@router.get('/searches', response_model=list[SearchOut], dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_searches(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.organization_id is None:
        return []
    base = (
        db.query(Search)
        .join(Client, Search.client_id == Client.id)
        .filter(Client.organization_id == user.organization_id, Search.archived_at.is_(None))
    )
    if user.role == 'SUPERADMIN':
        searches = base.order_by(Search.id).all()
        return [_serialize_search(search, db) for search in searches]
    client_ids = get_user_client_ids(user)
    if not client_ids:
        return []
    searches = base.filter(Search.client_id.in_(client_ids)).order_by(Search.id).all()
    return [_serialize_search(search, db) for search in searches]


@router.get('/searches/{search_id}', response_model=SearchOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def get_search(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    return _serialize_search(search, db)


@router.get('/candidates/bank/en-banca', response_model=list[CandidateBankOut], dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_en_banca_candidates(user=Depends(get_current_user), db: Session = Depends(get_db)):
    oid = require_organization_id(user)
    q = (
        db.query(Candidate)
        .join(Client, Candidate.client_id == Client.id)
        .filter(
            Candidate.status == 'en_banca',
            Client.organization_id == oid,
            Candidate.archived_at.is_(None),
        )
    )
    if user.role == 'COMERCIAL':
        cids = get_user_client_ids(user)
        if not cids:
            return []
        q = q.filter(Candidate.client_id.in_(cids))
    rows = q.order_by(Candidate.created_at.desc()).all()
    return [
        CandidateBankOut(
            id=c.id,
            full_name=c.full_name,
            email=c.email,
            short_profile=c.short_profile,
            status=c.status,
            created_at=c.created_at.isoformat() if c.created_at else None,
            client_id=c.client_id,
        )
        for c in rows
    ]


@router.get('/candidates', response_model=list[CandidateOut], dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_all_candidates(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.organization_id is None:
        return []
    client_ids = {c.id for c in get_accessible_clients(user, db)}
    if not client_ids and user.role != 'SUPERADMIN':
        return []
    q = db.query(Candidate).filter(Candidate.archived_at.is_(None))
    if user.role != 'SUPERADMIN':
        q = q.filter(Candidate.client_id.in_(client_ids))
    candidates = q.order_by(Candidate.id.desc()).all()
    return [_serialize_candidate(candidate, db, include_internal=True, viewer_role=user.role) for candidate in candidates]


@router.post('/candidates/{candidate_id}/assignments', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def assign_candidate(candidate_id: int, payload: CandidateAssignmentCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate or candidate.archived_at is not None:
        raise HTTPException(status_code=404, detail='Candidate not found')
    ensure_candidate_in_organization(db, user, candidate)
    if not payload.search_ids:
        raise HTTPException(status_code=400, detail='At least one search is required')
    first_search_id = None
    for search_id in payload.search_ids:
        search = db.get(Search, search_id)
        if not search or search.archived_at is not None:
            raise HTTPException(status_code=404, detail='Search not found')
        require_organization_id(user)
        if not can_access_client(user, search.client_id, db):
            raise HTTPException(status_code=404, detail='Search not found')
        assign_candidate_to_search(
            db,
            candidate=candidate,
            search=search,
            status=payload.status or 'en_revision',
            assigned_by_user_id=user.id,
            notes=payload.notes,
        )
        if first_search_id is None:
            first_search_id = search.id
    db.refresh(candidate)
    return _serialize_candidate(candidate, db, include_internal=True, viewer_role=user.role, search_id=first_search_id)


@router.get('/candidates/{candidate_id}', response_model=CandidateOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def get_candidate(candidate_id: int, search_id: int | None = Query(None), user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    context_search_id = _resolve_candidate_search_id(candidate, db, search_id)
    if context_search_id is not None:
        search = db.get(Search, context_search_id)
        if not search:
            raise HTTPException(status_code=404, detail='Search not found')
        if not can_access_client(user, search.client_id, db):
            raise HTTPException(status_code=404, detail='Candidate not found')
    else:
        if user.role == 'CLIENTE':
            raise HTTPException(status_code=404, detail='Candidate not found')
        try:
            ensure_candidate_in_organization(db, user, candidate)
        except HTTPException:
            raise HTTPException(status_code=404, detail='Candidate not found')
        if user.role == 'COMERCIAL' and candidate.client_id not in set(get_user_client_ids(user)):
            raise HTTPException(status_code=404, detail='Candidate not found')
    if _is_hidden_for_client(user, candidate, db, context_search_id):
        raise HTTPException(status_code=404, detail='Candidate not found')
    return _serialize_candidate(candidate, db, include_internal=user.role in ('COMERCIAL', 'TALENT', 'SUPERADMIN'), viewer_role=user.role, search_id=context_search_id)


@router.patch('/candidates/{candidate_id}', response_model=CandidateOut, dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def update_candidate(candidate_id: int, payload: CandidateUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    if candidate.search_id is not None:
        search = db.get(Search, candidate.search_id)
        if not search:
            raise HTTPException(status_code=404, detail='Search not found')
        if not can_access_client(user, search.client_id, db):
            raise HTTPException(status_code=404, detail='Candidate not found')
    else:
        if user.role not in ('TALENT', 'SUPERADMIN', 'COMERCIAL'):
            raise HTTPException(status_code=404, detail='Candidate not found')
        ensure_candidate_in_organization(db, user, candidate)
        if user.role == 'COMERCIAL' and candidate.client_id not in set(get_user_client_ids(user)):
            raise HTTPException(status_code=404, detail='Candidate not found')

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail='No fields to update')
    if 'search_id' in data and data['search_id'] is not None:
        search = db.get(Search, data['search_id'])
        if not search or search.archived_at is not None:
            raise HTTPException(status_code=404, detail='Search not found')
        if not can_access_client(user, search.client_id, db):
            raise HTTPException(status_code=404, detail='Search not found')
        if search.manual_state == 'cerrada':
            raise HTTPException(status_code=400, detail='Search is closed')
        assign_candidate_to_search(
            db,
            candidate=candidate,
            search=search,
            status=data.get('status') or 'en_revision',
            assigned_by_user_id=user.id,
        )
        if data.get('status') is None and candidate.status == 'en_banca':
            candidate.status = 'applied'
    if 'status' in data and data['status'] is not None:
        candidate.status = data['status']
        sync_assignment_status(db, candidate.id, _resolve_candidate_search_id(candidate, db), candidate.status)
        if data['status'] == 'descartado':
            candidate.archived_at = datetime.now(timezone.utc)
    if 'full_name' in data and data['full_name'] is not None:
        candidate.full_name = str(data['full_name']).strip()
    if 'email' in data:
        candidate.email = (str(data['email']).strip() if data['email'] else '') or None
    if 'short_profile' in data:
        candidate.short_profile = (str(data['short_profile'] or '').strip()) or None

    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db, include_internal=True, viewer_role=user.role)


@router.get('/searches/{search_id}/candidates', response_model=list[CandidateOut], dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_candidates(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    pairs = list_candidates_for_search(db, search_id, include_archived=user.role != 'CLIENTE')
    candidates = [candidate for candidate, _assignment in pairs]
    if user.role == 'CLIENTE':
        candidates = [c for c in candidates if is_presented_to_client(db, c.id, search_id)]
    include_internal = user.role in ('COMERCIAL', 'TALENT', 'SUPERADMIN')
    return [_serialize_candidate(candidate, db, include_internal=include_internal, viewer_role=user.role, search_id=search_id) for candidate in candidates]


@router.get('/searches/{search_id}/internal-notes', dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def get_search_internal_notes(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    return {'internal_notes': search.internal_notes or ''}


@router.patch('/searches/{search_id}/internal-notes', dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def update_search_internal_notes(search_id: int, payload: InternalNotesUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    search.internal_notes = (payload.internal_notes or '').strip() or None
    db.add(search)
    db.commit()
    return {'status': 'ok'}


@router.get('/metrics/summary', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def get_metrics_summary(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return build_metrics_summary(db, user)


@router.get('/candidates/{candidate_id}/internal-notes', dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def get_candidate_internal_notes(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    if candidate.search_id is not None:
        search = db.get(Search, candidate.search_id)
        if not search:
            raise HTTPException(status_code=404, detail='Search not found')
        if not can_access_client(user, search.client_id, db):
            raise HTTPException(status_code=404, detail='Search not found')
    else:
        try:
            ensure_candidate_in_organization(db, user, candidate)
        except HTTPException:
            raise HTTPException(status_code=404, detail='Candidate not found')
    return {'internal_notes': candidate.internal_notes or ''}


@router.patch('/candidates/{candidate_id}/internal-notes', dependencies=[Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def update_candidate_internal_notes(candidate_id: int, payload: InternalNotesUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    if candidate.search_id is not None:
        search = db.get(Search, candidate.search_id)
        if not search:
            raise HTTPException(status_code=404, detail='Search not found')
        if not can_access_client(user, search.client_id, db):
            raise HTTPException(status_code=404, detail='Search not found')
    else:
        try:
            ensure_candidate_in_organization(db, user, candidate)
        except HTTPException:
            raise HTTPException(status_code=404, detail='Candidate not found')
    candidate.internal_notes = (payload.internal_notes or '').strip() or None
    db.add(candidate)
    db.commit()
    return {'status': 'ok'}


@router.patch('/candidates/{candidate_id}/status', dependencies=[Depends(require_roles('CLIENTE'))])
def update_candidate_status(candidate_id: int, payload: CandidateStatusUpdate, search_id: int | None = Query(None), user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    context_search_id = _resolve_candidate_search_id(candidate, db, search_id)
    search = db.get(Search, context_search_id) if context_search_id is not None else None
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    if _is_hidden_for_client(user, candidate, db, context_search_id):
        raise HTTPException(status_code=404, detail='Candidate not found')

    status = payload.status
    if status == 'descartado':
        status = 'rechazado'
    if status not in {'en_revision', 'aprobado', 'rechazado'}:
        raise HTTPException(status_code=400, detail='Status not allowed for client')

    if status == 'rechazado':
        main_reason = (payload.feedback or {}).get('main_reason')
        if not main_reason or not str(main_reason).strip():
            raise HTTPException(status_code=400, detail='Feedback required for rejection')

    old_status = candidate.status
    candidate.status = status
    sync_assignment_status(db, candidate.id, context_search_id, status)

    history = StatusHistory(
        candidate_id=candidate.id,
        from_status=old_status,
        to_status=status,
        changed_by=user.id,
    )
    db.add(history)

    stage_map = {
        'en_revision': 'IN_REVIEW',
        'aprobado': 'APPROVED',
        'rechazado': 'REJECTED',
    }
    fb = Feedback(
        candidate_id=candidate.id,
        stage=stage_map.get(status, status.upper()),
        main_reason=str((payload.feedback or {}).get('main_reason') or status).strip(),
        ratings_json=(payload.feedback or {}).get('ratings_json'),
        comment=(payload.feedback or {}).get('comment'),
        created_by=user.id,
    )
    db.add(fb)

    db.add(candidate)
    db.commit()

    assigned = resolve_assigned_talent(db, search)
    notify_targets = [assigned] if assigned else []
    if not notify_targets:
        notify_targets = db.query(User).filter(User.role == 'TALENT', User.is_active.is_(True)).all()
    notify_users(
        db,
        [u for u in notify_targets if u],
        event_type='client_feedback_received',
        title='Feedback del cliente',
        message=f'El cliente registró "{status}" para {candidate.full_name} en {search.title}.',
        metadata={
            'client_id': search.client_id,
            'search_id': search.id,
            'search_title': search.title,
            'candidate_id': candidate.id,
            'candidate_name': candidate.full_name,
            'decision': status,
        },
        client_id=search.client_id,
        search_id=search.id,
        candidate_id=candidate.id,
    )
    return {'status': 'ok'}


@router.post('/candidates/{candidate_id}/feedback', dependencies=[Depends(require_roles('CLIENTE'))])
def create_feedback(candidate_id: int, payload: FeedbackCreate, search_id: int | None = Query(None), user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    context_search_id = _resolve_candidate_search_id(candidate, db, search_id)
    search = db.get(Search, context_search_id) if context_search_id is not None else None
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    if _is_hidden_for_client(user, candidate, db, context_search_id):
        raise HTTPException(status_code=404, detail='Candidate not found')

    fb = Feedback(
        candidate_id=candidate.id,
        stage=payload.stage,
        main_reason=payload.main_reason,
        ratings_json=payload.ratings_json,
        comment=payload.comment,
        created_by=user.id,
    )
    db.add(fb)
    db.commit()
    return {'status': 'ok'}


@router.post('/candidates/{candidate_id}/interviews', response_model=InterviewOut, dependencies=[Depends(require_roles('CLIENTE'))])
def book_interview(candidate_id: int, payload: InterviewCreate, search_id: int | None = Query(None), user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    context_search_id = _resolve_candidate_search_id(candidate, db, search_id)
    search = db.get(Search, context_search_id) if context_search_id is not None else None
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    if _is_hidden_for_client(user, candidate, db, context_search_id):
        raise HTTPException(status_code=404, detail='Candidate not found')

    slot = db.get(AvailabilitySlot, payload.slot_id)
    if not slot or slot.search_id != context_search_id:
        raise HTTPException(status_code=400, detail='Invalid slot')
    if slot.is_booked:
        raise HTTPException(status_code=400, detail='Slot already booked')

    slot.is_booked = True
    interview = Interview(candidate_id=candidate.id, slot_id=slot.id, status='pending')
    db.add(slot)
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.post('/interviews/{interview_id}/accept', dependencies=[Depends(require_roles('CLIENTE'))])
def accept_interview(interview_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail='Interview not found')
    candidate = db.get(Candidate, interview.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    if _is_hidden_for_client(user, candidate, db):
        raise HTTPException(status_code=404, detail='Candidate not found')
    if interview.status in ('cancelled', 'canceled'):
        raise HTTPException(status_code=400, detail='Interview is cancelled')

    interview.status = 'scheduled'
    db.add(interview)
    db.commit()
    return {'status': 'ok'}


@router.post('/interviews/{interview_id}/cancel', dependencies=[Depends(require_roles('CLIENTE'))])
def cancel_interview(interview_id: int, payload: InterviewCancelPayload, user=Depends(get_current_user), db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail='Interview not found')
    candidate = db.get(Candidate, interview.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    if _is_hidden_for_client(user, candidate, db):
        raise HTTPException(status_code=404, detail='Candidate not found')
    if interview.status in ('cancelled', 'canceled'):
        return {'status': 'ok'}

    reason = (payload.reason or '').strip()
    if interview.status == 'scheduled' and not reason:
        raise HTTPException(status_code=400, detail='Cancellation reason required for scheduled interviews')

    interview.status = 'cancelled'
    slot = db.get(AvailabilitySlot, interview.slot_id)
    if slot:
        slot.is_booked = False
        db.add(slot)
    db.add(interview)
    db.commit()

    create_event_notifications_for_roles(
        db,
        client_id=search.client_id,
        roles=['TALENT'],
        event_type='interview_cancelled_by_client',
        title='Entrevista cancelada por cliente',
        message=f'El cliente canceló entrevista de {candidate.full_name}.',
        metadata={
            'client_id': search.client_id,
            'search_id': search.id,
            'search_title': search.title,
            'candidate_id': candidate.id,
            'candidate_name': candidate.full_name,
            'interview_id': interview.id,
            'reason': reason or None,
        },
    )
    return {'status': 'ok'}


@router.get('/candidates/{candidate_id}/interviews', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_candidate_interviews(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=404, detail='Search not found')
    if _is_hidden_for_client(user, candidate, db):
        raise HTTPException(status_code=404, detail='Candidate not found')

    interviews = db.query(Interview).filter(Interview.candidate_id == candidate.id).order_by(Interview.id.desc()).all()
    result = []
    for interview in interviews:
        slot = db.get(AvailabilitySlot, interview.slot_id)
        result.append({
            'id': interview.id,
            'slot_id': interview.slot_id,
            'status': interview.status,
            'start_datetime': slot.start_datetime if slot else None,
            'end_datetime': slot.end_datetime if slot else None,
            'candidate_name': candidate.full_name,
            'cancellation_reason': _get_latest_cancel_reason(db, interview.id),
        })
    return result


