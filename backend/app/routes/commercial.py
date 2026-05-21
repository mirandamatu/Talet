from datetime import datetime, timezone
from io import BytesIO
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.client import Client
from app.models.search import Search
from app.models.search_ai_question import SearchAIQuestion
from app.models.search_document import SearchDocument
from app.models.user import User
from app.schemas.client import ClientOut, ClientSlugUpdate
from app.schemas.search import SearchCreate, SearchOut, SearchUpdate
from app.services.ai_engine import analyze_job_questions, extract_document_text
from app.services.ai_insights import create_ai_insight, get_search_questions_fields
from app.services.notifications import create_event_notifications_for_roles
from app.services.search_ai_questions import replace_search_ai_questions
from app.services.search_states import apply_manual_state_change, classify_search, get_search_candidate_counts
from app.services.storage import upload_document
from app.services.plan_limits import check_search_limit
from app.services.user_clients import require_client_access

router = APIRouter(prefix='/clients', tags=['commercial'])


def _serialize_search(search: Search, db: Session) -> dict:
    documents = db.query(SearchDocument).filter(SearchDocument.search_id == search.id).order_by(SearchDocument.id.desc()).all()
    question_rows = db.query(SearchAIQuestion).filter(SearchAIQuestion.search_id == search.id).order_by(SearchAIQuestion.id).all()
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
            {'id': row.id, 'search_id': row.search_id, 'question': row.question, 'answer': row.answer, 'status': row.status}
            for row in question_rows
        ],
        **get_search_questions_fields(db, search.id),
    }


@router.get('/{client_id}/searches', response_model=list[SearchOut], dependencies=[Depends(require_roles('COMERCIAL', 'SUPERADMIN'))])
def list_searches(client_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_client_access(user, client_id, db)
    searches = db.query(Search).filter(Search.client_id == client_id, Search.archived_at.is_(None)).order_by(Search.id).all()
    return [_serialize_search(search, db) for search in searches]


@router.post('/{client_id}/searches', response_model=SearchOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'SUPERADMIN'))])
async def create_search(
    client_id: int,
    request: Request,
    file: UploadFile | None = File(None),
    title: str | None = Form(None),
    job_description: str | None = Form(None),
    contact_name: str | None = Form(None),
    contact_email: str | None = Form(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_client_access(user, client_id, db)
    client_row = db.get(Client, client_id)
    if not client_row or client_row.organization_id is None:
        raise HTTPException(status_code=404, detail='Client not found')
    check_search_limit(db, client_row.organization_id)
    document_bytes: bytes | None = None
    extracted_text = ''
    if request.headers.get('content-type', '').startswith('application/json'):
        payload = SearchCreate(**(await request.json()))
        title = payload.title
        job_description = payload.job_description
        contact_name = payload.contact_name
        contact_email = payload.contact_email
    elif not title:
        form = await request.form()
        title = str(form.get('title') or '')
        job_description = str(form.get('job_description') or '')
        contact_name = str(form.get('contact_name') or '') or None
        contact_email = str(form.get('contact_email') or '') or None
        upload = form.get('file')
        if isinstance(upload, UploadFile):
            file = upload
    if file and file.filename:
        document_bytes = await file.read()
        extracted_text = extract_document_text(document_bytes, file.filename, file.content_type)
    if not title or not ((job_description or '').strip() or extracted_text):
        raise HTTPException(status_code=400, detail='Title and job description or document are required')
    final_description = (job_description or '').strip()
    if extracted_text:
        final_description = f"{final_description}\n\nTexto extraido del documento:\n{extracted_text}".strip()
    assigned_talent_id = user.id if user.role == 'TALENT' else None
    if assigned_talent_id is None:
        fallback = (
            db.query(User)
            .filter(User.role == 'TALENT', User.is_active.is_(True), User.organization_id == client_row.organization_id)
            .first()
        )
        assigned_talent_id = fallback.id if fallback else None
    search = Search(
        client_id=client_id,
        title=title,
        job_description=final_description,
        contact_name=contact_name,
        contact_email=contact_email,
        manual_state='abierta',
        assigned_talent_user_id=assigned_talent_id,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    if file and document_bytes is not None and file.filename:
        file_url = upload_document(BytesIO(document_bytes), file.filename, 'search-documents')
        db.add(SearchDocument(
            search_id=search.id,
            kind='job_description',
            file_name=file.filename,
            file_url=file_url,
            content_type=file.content_type,
            extracted_text=extracted_text,
            created_by=user.id,
        ))
        db.commit()
    try:
        ai_questions = analyze_job_questions(
            title=search.title,
            job_description=search.job_description,
        )
        create_ai_insight(
            db,
            entity_type='search',
            entity_id=search.id,
            kind='search_questions',
            score=None,
            recommendation=not ai_questions.get('needs_follow_up'),
            summary=ai_questions.get('summary'),
            payload_json={
                'needs_follow_up': bool(ai_questions.get('needs_follow_up')),
                'questions': ai_questions.get('questions') or [],
                'model': ai_questions.get('model') or 'heuristic',
            },
            created_by=user.id,
        )
        replace_search_ai_questions(db, search.id, ai_questions.get('questions') or [], user.id)
    except Exception:
        # AI must never block regular search creation.
        pass
    client = db.get(Client, client_id)
    client_name = client.name if client else f'Cliente {client_id}'
    summary = (search.job_description or '').strip().replace('\n', ' ')
    if len(summary) > 180:
        summary = f"{summary[:180].rstrip()}..."
    roles = ['TALENT', 'COMERCIAL'] if user.role == 'CLIENTE' else ['TALENT', 'CLIENTE']
    create_event_notifications_for_roles(
        db,
        client_id=client_id,
        roles=roles,
        event_type='new_search_opened',
        title='Nueva búsqueda abierta',
        message=f'{client_name} abrió la búsqueda "{search.title}".',
        metadata={
            'client_id': client_id,
            'client_name': client_name,
            'search_id': search.id,
            'search_title': search.title,
            'job_summary': summary,
        },
    )
    return _serialize_search(search, db)


@router.patch('/{client_id}/slug', response_model=ClientOut)
def update_client_slug(
    client_id: int,
    payload: ClientSlugUpdate,
    user=Depends(require_roles('COMERCIAL', 'TALENT', 'SUPERADMIN')),
    db: Session = Depends(get_db),
):
    require_client_access(user, client_id, db)
    raw = payload.public_slug.strip().lower()
    if not re.match(r'^[a-z0-9-]+$', raw):
        raise HTTPException(status_code=400, detail='Invalid slug format')
    taken = db.query(Client).filter(Client.public_slug == raw, Client.id != client_id).first()
    if taken:
        raise HTTPException(status_code=400, detail='Slug already in use')
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail='Client not found')
    client.public_slug = raw
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.patch('/{client_id}/searches/{search_id}', response_model=SearchOut, dependencies=[Depends(require_roles('CLIENTE', 'COMERCIAL', 'TALENT', 'SUPERADMIN'))])
def update_search(client_id: int, search_id: int, payload: SearchUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    require_client_access(user, client_id, db)
    search = db.get(Search, search_id)
    if not search or search.client_id != client_id:
        raise HTTPException(status_code=404, detail='Search not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == 'manual_state':
            normalized = (value or '').strip().lower() or None
            if normalized == 'cerrada':
                normalized = 'desactivada'
            if normalized not in (None, 'abierta', 'activa', 'desactivada', 'eliminada'):
                raise HTTPException(status_code=400, detail='Invalid search state')
            apply_manual_state_change(search, normalized)
            continue
        setattr(search, field, value)
    search.updated_at = datetime.now(timezone.utc)
    db.add(search)
    db.commit()
    db.refresh(search)
    if payload.job_description is not None or payload.title is not None:
        try:
            ai_questions = analyze_job_questions(
                title=search.title,
                job_description=search.job_description,
            )
            create_ai_insight(
                db,
                entity_type='search',
                entity_id=search.id,
                kind='search_questions',
                score=None,
                recommendation=not ai_questions.get('needs_follow_up'),
                summary=ai_questions.get('summary'),
                payload_json={
                    'needs_follow_up': bool(ai_questions.get('needs_follow_up')),
                    'questions': ai_questions.get('questions') or [],
                    'model': ai_questions.get('model') or 'heuristic',
                },
                created_by=user.id,
            )
            replace_search_ai_questions(db, search.id, ai_questions.get('questions') or [], user.id)
        except Exception:
            pass
    return _serialize_search(search, db)
