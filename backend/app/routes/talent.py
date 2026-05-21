from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.availability_slot import AvailabilitySlot
from app.models.candidate import Candidate
from app.models.search import Search
from app.models.user import User
from app.schemas.availability import AvailabilitySlotCreate, AvailabilitySlotOut
from app.schemas.candidate import CandidateOut
from app.services.ai_engine import analyze_candidate_fit, extract_pdf_text
from app.services.ai_insights import create_ai_insight, get_candidate_fit_fields
from app.services.mail_delivery import send_mail_acting_as_user
from app.services.mail_result import mail_result_or_raise
from app.services.notifications import notify_users
from app.services.presentations import is_presented_to_client, present_candidate
from app.services.storage import save_cv_local, upload_cv
from app.services.user_clients import require_client_access

router = APIRouter(tags=['talent'])


class PresentCandidateRequest(BaseModel):
    notes: str | None = None


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


@router.post('/searches/{search_id}/candidates', response_model=CandidateOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def create_candidate(
    search_id: int,
    full_name: str = Form(...),
    short_profile: str | None = Form(None),
    email: str | None = Form(None),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail='Only PDF allowed')

    pdf_bytes = file.file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail='Empty file')

    try:
        cv_url = upload_cv(BytesIO(pdf_bytes), file.filename)
    except Exception:
        # Last-resort fallback to avoid blocking candidate creation in dev/local.
        ext = file.filename[file.filename.rfind('.') :] if '.' in file.filename else ''
        local_key = f"cvs/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{search_id}{ext}"
        try:
            cv_url = save_cv_local(BytesIO(pdf_bytes), local_key)
        except Exception as local_exc:
            raise HTTPException(status_code=500, detail=f'Could not upload CV: {local_exc}')
    candidate = Candidate(
        search_id=search_id,
        full_name=full_name,
        email=email,
        short_profile=short_profile,
        cv_file_url=cv_url,
        cv_file_name=file.filename,
        cv_uploaded_at=datetime.now(timezone.utc),
        status='en_revision',
        source='manual',
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    try:
        cv_text = extract_pdf_text(pdf_bytes)
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
            kind='candidate_fit',
            score=fit.get('score'),
            recommendation=fit.get('recommendation'),
            summary=fit.get('summary'),
            payload_json={
                'reasons': fit.get('reasons') or [],
                'model': fit.get('model') or 'heuristic',
            },
            created_by=user.id,
        )
    except Exception:
        # AI analysis should not block candidate creation.
        pass
    client_name = search.client.name if getattr(search, 'client', None) else f'Cliente {search.client_id}'
    return _serialize_candidate(candidate, db)


@router.post('/candidates/{candidate_id}/present', dependencies=[Depends(require_roles('TALENT', 'COMERCIAL', 'SUPERADMIN'))])
def present_candidate_to_client(
    candidate_id: int,
    payload: PresentCandidateRequest | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    candidate = db.get(Candidate, candidate_id)
    if not candidate or not candidate.search_id:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    notes = payload.notes if payload else None
    row = present_candidate(
        db,
        candidate_id=candidate.id,
        search_id=search.id,
        presented_by=user.id,
        notes=notes,
    )
    client_users = db.query(User).filter(User.role == 'CLIENTE', User.is_active.is_(True)).all()
    client_users = [u for u in client_users if u.client_id == search.client_id or search.client_id in u.client_ids]
    notify_users(
        db,
        client_users,
        event_type='candidate_presented',
        title='Nuevo candidato presentado',
        message=f'Se presentó formalmente a {candidate.full_name} para "{search.title}".',
        metadata={
            'candidate_id': candidate.id,
            'search_id': search.id,
            'presentation_id': row.id,
        },
        client_id=search.client_id,
        search_id=search.id,
        candidate_id=candidate.id,
    )
    commercial_users = db.query(User).filter(User.role == 'COMERCIAL', User.is_active.is_(True)).all()
    notify_users(
        db,
        commercial_users,
        event_type='candidate_presented',
        title='Candidato presentado a cliente',
        message=f'{candidate.full_name} fue presentado en {search.title}.',
        metadata={'candidate_id': candidate.id, 'search_id': search.id},
        client_id=search.client_id,
        search_id=search.id,
        candidate_id=candidate.id,
    )
    return {
        'status': 'presented',
        'presentation_id': row.id,
        'presented_at': row.presented_at.isoformat() if row.presented_at else None,
        'is_presented_to_client': True,
    }


@router.post('/candidates/{candidate_id}/confirm-send', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def confirm_send(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return present_candidate_to_client(candidate_id, PresentCandidateRequest(), user, db)


@router.get('/searches/{search_id}/availability-slots', response_model=list[AvailabilitySlotOut], dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN', 'CLIENTE', 'COMERCIAL'))])
def list_slots(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    return db.query(AvailabilitySlot).filter(AvailabilitySlot.search_id == search_id).order_by(AvailabilitySlot.start_datetime).all()


@router.post('/searches/{search_id}/availability-slots', response_model=AvailabilitySlotOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def create_slot(search_id: int, payload: AvailabilitySlotCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    _validate_slot_datetimes(payload.start_datetime, payload.end_datetime)
    slot = AvailabilitySlot(
        search_id=search_id,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        is_booked=False,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@router.patch('/availability-slots/{slot_id}', response_model=AvailabilitySlotOut, dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def update_slot(slot_id: int, payload: AvailabilitySlotCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    slot = db.get(AvailabilitySlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail='Slot not found')
    search = db.get(Search, slot.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    if slot.is_booked:
        raise HTTPException(status_code=400, detail='Cannot edit a booked slot')
    _validate_slot_datetimes(payload.start_datetime, payload.end_datetime)

    slot.start_datetime = payload.start_datetime
    slot.end_datetime = payload.end_datetime
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@router.delete('/availability-slots/{slot_id}', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def delete_slot(slot_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    slot = db.get(AvailabilitySlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail='Slot not found')
    search = db.get(Search, slot.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    if slot.is_booked:
        raise HTTPException(status_code=400, detail='Slot already booked')
    db.delete(slot)
    db.commit()
    return {'status': 'ok'}


@router.post('/candidates/{candidate_id}/archive', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def archive_candidate(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    candidate.archived_at = datetime.now(timezone.utc)
    db.add(candidate)
    db.commit()
    return {'status': 'ok'}


@router.post('/candidates/{candidate_id}/unarchive', dependencies=[Depends(require_roles('TALENT', 'SUPERADMIN'))])
def unarchive_candidate(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail='Candidate not found')
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail='Search not found')
    require_client_access(user, search.client_id, db)
    candidate.archived_at = None
    db.add(candidate)
    db.commit()
    return {'status': 'ok'}


def _validate_slot_datetimes(start_dt: datetime, end_dt: datetime) -> None:
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail='End datetime must be after start datetime')
