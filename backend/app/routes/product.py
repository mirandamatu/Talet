from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.calendar_event import CalendarEvent
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.search import Search
from app.models.search_ai_question import SearchAIQuestion
from app.models.search_document import SearchDocument
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.models.user_email_setting import UserEmailSetting
from app.schemas.calendar import CalendarEventCreate, CalendarEventOut
from app.schemas.candidate import CandidateOut
from app.schemas.email_settings import EmailSettingsIn, EmailSettingsOut
from app.schemas.search import SearchOut, SearchUpdate
from app.services.ai_engine import analyze_candidate_fit, analyze_job_questions, extract_document_text, extract_pdf_text, regenerate_job_description
from app.services.ai_insights import create_ai_insight, get_candidate_fit_fields, get_search_questions_fields
from app.services.mail_delivery import send_mail_acting_as_user
from app.services.mail_result import mail_result_or_raise
from app.services.notifications import create_event_notifications_for_roles
from app.services.search_ai_questions import replace_search_ai_questions
from app.services.search_states import apply_manual_state_change, classify_search, get_search_candidate_counts, normalize_manual_state
from app.services.storage import upload_cv, upload_document
from app.services.tenancy import ensure_candidate_in_organization, require_organization_id
from app.services.user_clients import can_access_client, get_accessible_clients, get_user_client_ids, require_client_access
from app.services.user_preferences import get_or_create_preferences, serialize_preferences
from pydantic import BaseModel


class UserPreferencesUpdate(BaseModel):
    notification_settings: dict | None = None
    reminder_settings: dict | None = None
    default_stale_search_days: int | None = None
    default_no_response_days: int | None = None

router = APIRouter(tags=['product-upgrade'])


def _email_settings_out(setting: UserEmailSetting | None) -> dict:
    if not setting:
        return {
            'smtp_host': None,
            'smtp_port': 587,
            'smtp_user': None,
            'smtp_from_email': None,
            'use_tls': True,
            'is_configured': False,
            'has_password': False,
        }
    return {
        'smtp_host': setting.smtp_host,
        'smtp_port': setting.smtp_port,
        'smtp_user': setting.smtp_user,
        'smtp_from_email': setting.smtp_from_email,
        'use_tls': setting.use_tls,
        'is_configured': setting.is_configured,
        'has_password': bool(setting.smtp_password),
    }




def _calendar_event_out(event: CalendarEvent, *, mail_warnings: list[str] | None = None, mails_sent: int = 0) -> dict:
    return {
        'id': event.id,
        'title': event.title,
        'start_datetime': event.start_datetime,
        'end_datetime': event.end_datetime,
        'kind': event.kind,
        'status': event.status,
        'notes': event.notes,
        'meeting_url': event.meeting_url,
        'organizer_email': event.organizer_email,
        'google_event_id': event.google_event_id,
        'invite_emails': event.invite_emails_json or [],
        'invited_user_ids': event.invited_user_ids_json or [],
        'role_scope': event.role_scope,
        'client_id': event.client_id,
        'search_id': event.search_id,
        'candidate_id': event.candidate_id,
        'created_by': event.created_by,
        'mail_warnings': mail_warnings or [],
        'mails_sent': mails_sent,
    }


def _event_notification_exists(db: Session, to_email: str, event_type: str, event_id: int) -> bool:
    matches = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.type == 'event',
            NotificationLog.to_email == to_email,
            NotificationLog.error.contains(f'"event_type": "{event_type}"'),
            NotificationLog.error.contains(f'"event_id": {event_id}'),
        )
        .first()
    )
    return matches is not None


def _create_direct_event_notification(
    db: Session,
    *,
    to_email: str,
    event_type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> bool:
    event_id = (metadata or {}).get('event_id')
    if event_id and _event_notification_exists(db, to_email, event_type, int(event_id)):
        return False
    payload = {
        'event_type': event_type,
        'title': title,
        'message': message,
        'metadata': metadata or {},
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    db.add(NotificationLog(type='event', to_email=to_email, status='unread', retries=0, error=json.dumps(payload, ensure_ascii=False)))
    return True


def _serialize_candidate(candidate: Candidate, db: Session) -> dict:
    return {
        'id': candidate.id,
        'search_id': candidate.search_id,
        'full_name': candidate.full_name,
        'email': candidate.email,
        'short_profile': candidate.short_profile,
        'cv_file_url': candidate.cv_file_url,
        'cv_file_name': candidate.cv_file_name,
        'cv_uploaded_at': candidate.cv_uploaded_at.isoformat() if candidate.cv_uploaded_at else None,
        'status': candidate.status,
        'archived_at': candidate.archived_at.isoformat() if candidate.archived_at else None,
        'discarded_reason': None,
        'discarded_comment': None,
        'internal_notes': candidate.internal_notes,
        'has_client_feedback': False,
        'latest_client_feedback_reason': None,
        'client_feedback': [],
        **get_candidate_fit_fields(db, candidate.id),
    }


def _serialize_search(search: Search, db: Session) -> dict:
    documents = db.query(SearchDocument).filter(SearchDocument.search_id == search.id).order_by(SearchDocument.id.desc()).all()
    questions = db.query(SearchAIQuestion).filter(SearchAIQuestion.search_id == search.id).order_by(SearchAIQuestion.id).all()
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
            {'id': row.id, 'search_id': row.search_id, 'question': row.question, 'answer': row.answer, 'status': row.status}
            for row in questions
        ],
        **get_search_questions_fields(db, search.id),
    }


def _assert_search_access(user, search: Search, db: Session) -> None:
    if not can_access_client(user, search.client_id, db):
        raise HTTPException(status_code=403, detail='Forbidden')


@router.get('/me/preferences', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def get_my_preferences(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_preferences(get_or_create_preferences(db, user.id))


@router.patch('/me/preferences', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def update_my_preferences(payload: UserPreferencesUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = get_or_create_preferences(db, user.id)
    data = payload.model_dump(exclude_unset=True)
    if 'notification_settings' in data and data['notification_settings'] is not None:
        prefs.notification_settings_json = data['notification_settings']
    if 'reminder_settings' in data and data['reminder_settings'] is not None:
        prefs.reminder_settings_json = data['reminder_settings']
    if 'default_stale_search_days' in data and data['default_stale_search_days'] is not None:
        prefs.default_stale_search_days = data['default_stale_search_days']
    if 'default_no_response_days' in data and data['default_no_response_days'] is not None:
        prefs.default_no_response_days = data['default_no_response_days']
    prefs.updated_at = datetime.now(timezone.utc)
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return serialize_preferences(prefs)


@router.get('/me/email-settings', response_model=EmailSettingsOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def get_my_email_settings(user=Depends(get_current_user), db: Session = Depends(get_db)):
    setting = db.query(UserEmailSetting).filter(UserEmailSetting.user_id == user.id).first()
    return _email_settings_out(setting)


@router.put('/me/email-settings', response_model=EmailSettingsOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def save_my_email_settings(payload: EmailSettingsIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    setting = db.query(UserEmailSetting).filter(UserEmailSetting.user_id == user.id).first()
    if not setting:
        setting = UserEmailSetting(user_id=user.id)
    setting.smtp_host = (payload.smtp_host or '').strip() or None
    setting.smtp_port = payload.smtp_port or 587
    setting.smtp_user = (payload.smtp_user or '').strip() or None
    if payload.smtp_password is not None and payload.smtp_password.strip():
        setting.smtp_password = payload.smtp_password.strip()
    setting.smtp_from_email = (payload.smtp_from_email or '').strip() or user.email
    setting.use_tls = payload.use_tls
    setting.is_configured = bool(setting.smtp_host and setting.smtp_from_email)
    setting.updated_at = datetime.now(timezone.utc)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return _email_settings_out(setting)


@router.post('/me/email-settings/use-google-only', response_model=EmailSettingsOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def use_google_only_for_mail(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Desactiva SMTP manual del perfil para que Gmail OAuth sea el canal de envío."""
    setting = db.query(UserEmailSetting).filter(UserEmailSetting.user_id == user.id).first()
    if not setting:
        setting = UserEmailSetting(user_id=user.id, is_configured=False)
    else:
        setting.is_configured = False
    setting.updated_at = datetime.now(timezone.utc)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return _email_settings_out(setting)


@router.patch('/searches/{search_id}', response_model=SearchOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'SUPERADMIN'))])
def update_search(search_id: int, payload: SearchUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    _assert_search_access(user, search, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == 'manual_state':
            normalized = normalize_manual_state(value)
            if normalized not in (None, 'abierta', 'activa', 'desactivada', 'eliminada'):
                raise HTTPException(status_code=400, detail='Invalid search state')
            apply_manual_state_change(search, normalized)
            continue
        setattr(search, field, value)
    search.updated_at = datetime.now(timezone.utc)
    db.add(search)
    db.commit()
    db.refresh(search)
    if payload.title is not None or payload.job_description is not None:
        analysis = analyze_job_questions(title=search.title, job_description=search.job_description)
        create_ai_insight(
            db,
            entity_type='search',
            entity_id=search.id,
            kind='search_questions',
            recommendation=not analysis.get('needs_follow_up'),
            summary=analysis.get('summary'),
            payload_json={
                'needs_follow_up': bool(analysis.get('needs_follow_up')),
                'questions': analysis.get('questions') or [],
                'model': analysis.get('model') or 'heuristic',
            },
            created_by=user.id,
        )
        replace_search_ai_questions(db, search.id, analysis.get('questions') or [], user.id)
    return _serialize_search(search, db)


@router.delete('/searches/{search_id}', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'SUPERADMIN'))])
def archive_search(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    _assert_search_access(user, search, db)
    search.archived_at = datetime.now(timezone.utc)
    db.add(search)
    db.commit()
    return {'status': 'ok'}


@router.post('/searches/{search_id}/documents', response_model=SearchOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'SUPERADMIN'))])
async def upload_search_document(
    search_id: int,
    kind: str = Form('job_description'),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail='Search not found')
    _assert_search_access(user, search, db)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail='Empty file')
    text = extract_document_text(raw, file.filename, file.content_type)
    file_url = upload_document(BytesIO(raw), file.filename, 'search-documents')
    db.add(SearchDocument(
        search_id=search.id,
        kind=kind,
        file_name=file.filename,
        file_url=file_url,
        content_type=file.content_type,
        extracted_text=text,
        created_by=user.id,
    ))
    if kind == 'job_description' and text:
        search.job_description = f"{search.job_description}\n\nTexto extraido del documento:\n{text}".strip()
        db.add(search)
    db.commit()
    return _serialize_search(search, db)


@router.post('/searches/{search_id}/meeting-upload', response_model=SearchOut, dependencies=[Depends(require_roles('COMERCIAL', 'SUPERADMIN'))])
async def upload_meeting(search_id: int, file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail='Search not found')
    _assert_search_access(user, search, db)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail='Empty file')
    file_url = upload_document(BytesIO(raw), file.filename, 'search-meetings')
    db.add(SearchDocument(
        search_id=search.id,
        kind='client_meeting',
        file_name=file.filename,
        file_url=file_url,
        content_type=file.content_type,
        extracted_text=extract_document_text(raw, file.filename, file.content_type),
        created_by=user.id,
    ))
    db.commit()
    return _serialize_search(search, db)


@router.post('/searches/{search_id}/ai/questions/{question_id}/answer', response_model=SearchOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'SUPERADMIN'))])
def answer_ai_question(search_id: int, question_id: int, answer: str = Form(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    _assert_search_access(user, search, db)
    question = db.get(SearchAIQuestion, question_id)
    if not question or question.search_id != search_id:
        raise HTTPException(status_code=404, detail='Question not found')
    question.answer = answer
    question.status = 'answered'
    question.answered_by = user.id
    question.updated_at = datetime.now(timezone.utc)
    db.add(question)
    db.commit()
    answered_rows = (
        db.query(SearchAIQuestion)
        .filter(SearchAIQuestion.search_id == search_id, SearchAIQuestion.status == 'answered')
        .order_by(SearchAIQuestion.id)
        .all()
    )
    search.job_description = regenerate_job_description(
        title=search.title,
        job_description=search.job_description,
        answers=[{'question': row.question, 'answer': row.answer or ''} for row in answered_rows],
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    return _serialize_search(search, db)


@router.post('/searches/{search_id}/ai/questions/skip', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'SUPERADMIN'))])
def skip_ai_questions(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    _assert_search_access(user, search, db)
    now = datetime.now(timezone.utc)
    rows = db.query(SearchAIQuestion).filter(SearchAIQuestion.search_id == search_id, SearchAIQuestion.status == 'pending').all()
    for row in rows:
        row.status = 'skipped'
        row.answered_by = user.id
        row.updated_at = now
        db.add(row)
    db.commit()
    return {'status': 'ok', 'updated': len(rows)}


@router.get('/calendar/invite-users', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_calendar_invite_users(user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(User).filter(User.is_active.is_(True))
    if user.role != 'SUPERADMIN':
        client_ids = get_user_client_ids(user)
        query = query.filter(or_(User.client_id.in_(client_ids), User.client_links.any()))
    rows = query.order_by(User.full_name, User.email).all()
    out = []
    for row in rows:
        if user.role != 'SUPERADMIN' and not any(cid in get_user_client_ids(row) for cid in get_user_client_ids(user)):
            continue
        out.append({'id': row.id, 'full_name': row.full_name, 'email': row.email, 'role': row.role})
    return out


@router.get('/calendar/events', response_model=list[CalendarEventOut], dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def list_calendar_events(user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(CalendarEvent)
    if user.role != 'SUPERADMIN':
        client_ids = get_user_client_ids(user)
        query = query.filter(or_(
            CalendarEvent.client_id.in_(client_ids),
            CalendarEvent.role_scope == user.role,
            CalendarEvent.created_by == user.id,
        ))
    events = query.order_by(CalendarEvent.start_datetime).all()
    if user.role != 'SUPERADMIN':
        invited_events = db.query(CalendarEvent).order_by(CalendarEvent.start_datetime).all()
        by_id = {event.id: event for event in events}
        for event in invited_events:
            if user.id in (event.invited_user_ids_json or []):
                by_id[event.id] = event
        events = sorted(by_id.values(), key=lambda item: item.start_datetime)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    changed = False
    for event in events:
        hours_until = (event.start_datetime - now).total_seconds() / 3600
        if 0 <= hours_until <= 24:
            message = f'El evento "{event.title}" empieza el {event.start_datetime.strftime("%d/%m/%Y %H:%M")}.'
            if _create_direct_event_notification(
                db,
                to_email=user.email,
                event_type='calendar_event_reminder',
                title='Recordatorio de calendario',
                message=message,
                metadata={'event_id': event.id, 'event_title': event.title, 'start_datetime': event.start_datetime.isoformat()},
            ):
                changed = True
    if changed:
        db.commit()
    return [_calendar_event_out(event) for event in events]


@router.post('/calendar/events', response_model=CalendarEventOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def create_calendar_event(payload: CalendarEventCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.end_datetime <= payload.start_datetime:
        raise HTTPException(status_code=400, detail='End datetime must be after start datetime')
    if payload.client_id is not None:
        require_client_access(user, payload.client_id, db)
    invite_emails = sorted(set(email.strip() for email in payload.invite_emails if email and email.strip()))
    invited_user_ids = sorted(set(int(user_id) for user_id in payload.invited_user_ids))
    event = CalendarEvent(
        title=payload.title,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        kind=payload.kind,
        notes=payload.notes,
        meeting_url=payload.meeting_url,
        invite_emails_json=invite_emails,
        invited_user_ids_json=invited_user_ids,
        role_scope=payload.role_scope,
        client_id=payload.client_id,
        search_id=payload.search_id,
        candidate_id=payload.candidate_id,
        created_by=user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    invited_users = db.query(User).filter(User.id.in_(invited_user_ids), User.is_active.is_(True)).all() if invited_user_ids else []
    all_emails = sorted(set(invite_emails + [row.email for row in invited_users if row.email]))
    message = f'Te agendaron "{event.title}" para el {event.start_datetime.strftime("%d/%m/%Y %H:%M")}.'
    if event.meeting_url:
        message = f'{message} Link: {event.meeting_url}'
    for invited in invited_users:
        _create_direct_event_notification(
            db,
            to_email=invited.email,
            event_type='calendar_event_scheduled',
            title='Nueva reunión agendada',
            message=message,
            metadata={'event_id': event.id, 'event_title': event.title, 'meeting_url': event.meeting_url, 'start_datetime': event.start_datetime.isoformat()},
        )
    if invited_users:
        db.commit()
    mail_warnings: list[str] = []
    mails_sent = 0
    for email in all_emails:
        result = send_mail_acting_as_user(db, user.id, email, f'Invitación: {event.title}', message)
        if result.get('status') == 'sent':
            mails_sent += 1
        else:
            mail_warnings.append(f'{email}: {result.get("message") or result.get("status")}')
    return _calendar_event_out(event, mail_warnings=mail_warnings, mails_sent=mails_sent)


@router.delete('/calendar/events/{event_id}', dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def delete_calendar_event(event_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(CalendarEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail='Event not found')
    if event.created_by != user.id and (event.client_id is None or not can_access_client(user, event.client_id, db)):
        raise HTTPException(status_code=403, detail='Forbidden')
    db.delete(event)
    db.commit()
    return {'status': 'ok'}


@router.get('/talent-bank/candidates', response_model=list[CandidateOut], dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def list_talent_bank(user=Depends(get_current_user), db: Session = Depends(get_db)):
    oid = require_organization_id(user)
    candidates = (
        db.query(Candidate)
        .join(Client, Candidate.client_id == Client.id)
        .filter(
            Candidate.search_id.is_(None),
            Candidate.archived_at.is_(None),
            Client.organization_id == oid,
        )
        .order_by(Candidate.id.desc())
        .all()
    )
    return [_serialize_candidate(candidate, db) for candidate in candidates]


@router.post('/talent-bank/candidates', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
async def create_talent_bank_candidate(
    full_name: str = Form(...),
    email: str | None = Form(None),
    short_profile: str | None = Form(None),
    client_id: int | None = Form(None),
    file: UploadFile | None = File(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accessible = get_accessible_clients(user, db)
    if not accessible:
        raise HTTPException(status_code=400, detail='No accessible client')
    if client_id is not None:
        target = next((c for c in accessible if c.id == client_id), None)
        if not target:
            raise HTTPException(status_code=404, detail='Client not found')
        chosen_id = target.id
    else:
        chosen_id = accessible[0].id
    cv_url = None
    cv_name = None
    uploaded_at = None
    if file and file.filename:
        raw = await file.read()
        if raw:
            cv_url = upload_cv(BytesIO(raw), file.filename)
            cv_name = file.filename
            uploaded_at = datetime.now(timezone.utc)
    candidate = Candidate(
        search_id=None,
        client_id=chosen_id,
        full_name=full_name,
        email=email,
        short_profile=short_profile,
        cv_file_url=cv_url,
        cv_file_name=cv_name,
        cv_uploaded_at=uploaded_at,
        status='banco_talent',
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db)


@router.patch('/talent-bank/candidates/{candidate_id}', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
async def update_talent_bank_candidate(
    candidate_id: int,
    full_name: str = Form(...),
    email: str | None = Form(None),
    short_profile: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate or candidate.search_id is not None or candidate.archived_at is not None:
        raise HTTPException(status_code=404, detail='Candidate not found in talent bank')
    candidate.full_name = full_name
    candidate.email = email
    candidate.short_profile = short_profile
    if file and file.filename:
        raw = await file.read()
        if raw:
            candidate.cv_file_url = upload_cv(BytesIO(raw), file.filename)
            candidate.cv_file_name = file.filename
            candidate.cv_uploaded_at = datetime.now(timezone.utc)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db)


@router.delete('/talent-bank/candidates/{candidate_id}', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def delete_talent_bank_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate or candidate.search_id is not None:
        raise HTTPException(status_code=404, detail='Candidate not found in talent bank')
    candidate.status = 'banco_no_activo'
    db.add(candidate)
    db.commit()
    return {'status': 'ok'}


@router.post('/talent-bank/candidates/{candidate_id}/activate', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def activate_talent_bank_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate or candidate.search_id is not None or candidate.archived_at is not None:
        raise HTTPException(status_code=404, detail='Candidate not found in talent bank')
    candidate.status = 'banco_talent'
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db)


@router.post('/talent-bank/candidates/{candidate_id}/assign-search/{search_id}', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def assign_talent_bank_candidate_to_search(candidate_id: int, search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate or candidate.search_id is not None or candidate.archived_at is not None:
        raise HTTPException(status_code=404, detail='Candidate not found in talent bank')
    try:
        ensure_candidate_in_organization(db, user, candidate)
    except HTTPException:
        raise HTTPException(status_code=404, detail='Candidate not found in talent bank')
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    candidate.search_id = search.id
    candidate.client_id = search.client_id
    candidate.status = 'en_revision'
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db)


@router.post('/candidates/{candidate_id}/send-to-bank', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def send_candidate_to_bank(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    if candidate.search_id is not None:
        search = db.get(Search, candidate.search_id)
        if search:
            require_client_access(user, search.client_id, db)
            candidate.client_id = search.client_id
    candidate.search_id = None
    candidate.status = 'banco_talent'
    candidate.archived_at = None
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db)


@router.delete('/candidates/{candidate_id}', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def delete_candidate(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    if candidate.search_id is not None:
        search = db.get(Search, candidate.search_id)
        if search:
            require_client_access(user, search.client_id, db)
    else:
        try:
            ensure_candidate_in_organization(db, user, candidate)
        except HTTPException:
            raise HTTPException(status_code=404, detail='Candidate not found')
    candidate.archived_at = datetime.now(timezone.utc)
    db.add(candidate)
    db.commit()
    return {'status': 'ok'}


@router.post('/talent-bank/recommend/{search_id}', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def recommend_from_bank(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    oid = require_organization_id(user)
    candidates = (
        db.query(Candidate)
        .join(Client, Candidate.client_id == Client.id)
        .filter(
            Candidate.search_id.is_(None),
            Candidate.archived_at.is_(None),
            Client.organization_id == oid,
        )
        .order_by(Candidate.id.desc())
        .all()
    )
    recommendations = []
    for candidate in candidates:
        cv_text = ''
        if candidate.cv_file_url and candidate.cv_file_url.startswith('/uploads/'):
            from pathlib import Path
            full_path = Path(__file__).resolve().parents[2] / candidate.cv_file_url.lstrip('/')
            if full_path.exists():
                cv_text = extract_pdf_text(full_path.read_bytes())
        fit = analyze_candidate_fit(
            search_title=search.title,
            job_description=search.job_description,
            candidate_name=candidate.full_name,
            short_profile=candidate.short_profile,
            cv_text=cv_text,
        )
        create_ai_insight(
            db,
            entity_type='candidate',
            entity_id=candidate.id,
            kind=f'bank_recommendation_search_{search.id}',
            score=fit.get('score'),
            recommendation=fit.get('recommendation'),
            summary=fit.get('summary'),
            payload_json={'reasons': fit.get('reasons') or [], 'search_id': search.id, 'model': fit.get('model') or 'heuristic'},
            created_by=user.id,
        )
        data = _serialize_candidate(candidate, db)
        data.update({
            'recommended_score': fit.get('score'),
            'recommended_summary': fit.get('summary'),
            'recommended_recommendation': bool(fit.get('recommendation') or (fit.get('score') or 0) >= 60),
            'recommended_reasons': fit.get('reasons') or [],
        })
        recommendations.append(data)
    recommendations.sort(key=lambda item: (
        1 if item.get('status') == 'banco_no_activo' else 0,
        -(item.get('recommended_score') or 0),
    ))
    return {'search_id': search.id, 'candidates': recommendations}


@router.post('/talent-bank/candidates/{candidate_id}/contact', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def contact_bank_candidate(candidate_id: int, search_id: int = Form(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    search = db.get(Search, search_id)
    if not candidate or candidate.search_id is not None:
        raise HTTPException(status_code=404, detail='Candidate not found in talent bank')
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    if not candidate.email:
        return {'status': 'skipped', 'message': 'Candidate email missing'}
    body = (
        f"Hola {candidate.full_name},\n\n"
        f"Tenemos una busqueda activa que podria interesarte: {search.title}.\n"
        "Queriamos saber si estas en busqueda activa o abierto/a a conversar.\n\n"
        "Saludos,\nEquipo Atipia"
    )
    result = send_mail_acting_as_user(db, user.id, candidate.email, f'Oportunidad laboral: {search.title}', body)
    mail_result_or_raise(result)
    return {
        'status': 'sent',
        'message': result.get('message', 'Correo enviado'),
        'mail_sent_via': result.get('via'),
        'mail_delivery_detail': result.get('message'),
    }


@router.patch('/candidates/{candidate_id}/cv', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
async def replace_candidate_cv(candidate_id: int, file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    if candidate.search_id is not None:
        search = db.get(Search, candidate.search_id)
        if search:
            require_client_access(user, search.client_id, db)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail='Empty file')
    candidate.cv_file_url = upload_cv(BytesIO(raw), file.filename)
    candidate.cv_file_name = file.filename
    candidate.cv_uploaded_at = datetime.now(timezone.utc)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db)


@router.delete('/candidates/{candidate_id}/cv', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def delete_candidate_cv(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    if candidate.search_id is not None:
        search = db.get(Search, candidate.search_id)
        if search:
            require_client_access(user, search.client_id, db)
    candidate.cv_file_url = None
    candidate.cv_file_name = None
    candidate.cv_uploaded_at = None
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, db)
