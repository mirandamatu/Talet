from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import mammoth
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.calendar_event import CalendarEvent
from app.models.candidate import Candidate
from app.models.candidate_search_assignment import CandidateSearchAssignment
from app.models.client import Client
from app.models.candidate_note import CandidateNote
from app.models.candidate_outreach import CandidateOutreach
from app.models.candidate_outreach_token import CandidateOutreachToken
from app.models.google_calendar_connection import GoogleCalendarConnection
from app.models.interview import Interview
from app.models.interview_transcript import InterviewTranscript
from app.models.search import Search
from app.models.search_candidate_analysis import SearchCandidateAnalysis
from app.models.user import User
from app.schemas.recruiting import (
    CandidateNoteCreate,
    CandidateNoteOut,
    CandidateNoteUpdate,
    CandidateOutreachOut,
    CandidateReplyOut,
    CvHtmlOut,
    GoogleCalendarStatusOut,
    InterviewProposalChoiceRequest,
    InterviewProposalRequest,
    MailDraftOut,
    MailDraftRequest,
    MailSendRequest,
    SearchCandidateAnalysesOut,
    SearchCandidateAnalysisOut,
    TranscriptOut,
    TranscriptUpsertRequest,
)
from app.services.activity import log_activity
from app.services.candidate_analysis import serialize_analysis, upsert_search_candidate_analysis
from app.services.client_context import build_client_context
from app.services.ai_agents import matching_agent
from app.services.ai_engine import extract_docx_text, extract_pdf_text
from app.services.candidate_notes import can_user_view_note, replace_note_visibility, serialize_note, touch_note
from app.services.mail_delivery import send_mail_acting_as_user, user_can_send_mail
from app.services.mail_result import mail_result_or_raise
from app.services.google_calendar import build_google_oauth_url, create_calendar_event, google_oauth_env_configured, oauth_scope_string
from app.services.google_gmail import google_connection_can_send_mail
from app.services.mail_drafts import generate_mail_draft
from app.services.notifications import create_event_notifications_for_roles, create_event_notifications_for_user_ids
from app.services.storage import upload_document
from app.services.search_states import classify_search
from app.services.user_clients import can_access_client, require_client_access
from app.services.candidate_assignments import PROJECT_STATUSES

router = APIRouter(tags=["recruiting"])


def _serialize_outreach(row: CandidateOutreach) -> dict:
    return {
        "id": row.id,
        "candidate_id": row.candidate_id,
        "search_id": row.search_id,
        "kind": row.kind,
        "subject": row.subject,
        "body": row.body,
        "status": row.status,
        "sent_by_user_id": row.sent_by_user_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
    }


def _reply_url(token: str, action: str) -> str:
    base = "/api/recruiting/outreach/reply"
    return f"{base}/{quote(token)}?action={quote(action)}"


def _candidate_access_search(user, candidate: Candidate, db: Session) -> Search | None:
    if candidate.search_id is None:
        return None
    search = db.get(Search, candidate.search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    require_client_access(user, search.client_id, db)
    return search


@router.post(
    "/searches/{search_id}/ai/analyze-candidates",
    response_model=SearchCandidateAnalysesOut,
    dependencies=[Depends(require_roles("TALENT"))],
)
def analyze_candidates_for_search(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail="Search not found")
    require_client_access(user, search.client_id, db)

    org_id = db.get(Client, search.client_id).organization_id if db.get(Client, search.client_id) else None
    candidate_query = db.query(Candidate).filter(Candidate.archived_at.is_(None))
    if org_id is not None:
        org_clients = [row.id for row in db.query(Client.id).filter(Client.organization_id == org_id).all()]
        candidate_query = candidate_query.filter(Candidate.client_id.in_(org_clients))
    busy_ids = [
        row.candidate_id
        for row in db.query(CandidateSearchAssignment.candidate_id)
        .join(Search, Search.id == CandidateSearchAssignment.search_id)
        .filter(
            CandidateSearchAssignment.archived_at.is_(None),
            CandidateSearchAssignment.status.in_(PROJECT_STATUSES),
            Search.archived_at.is_(None),
        )
        .all()
    ]
    if busy_ids:
        candidate_query = candidate_query.filter(Candidate.id.notin_(busy_ids))
    candidates = candidate_query.order_by(Candidate.id.desc()).limit(250).all()
    items: list[dict] = []
    for candidate in candidates:
        row = upsert_search_candidate_analysis(db, search=search, candidate=candidate, created_by=user.id)
        if float(row.match_score or 0) >= 7:
            items.append(serialize_analysis(row, candidate.full_name))
    items.sort(key=lambda item: float(item.get("match_score") or 0), reverse=True)
    return {"search_id": search.id, "items": items}


@router.post(
    "/searches/{search_id}/ai/match-candidates",
    response_model=SearchCandidateAnalysesOut,
    dependencies=[Depends(require_roles("TALENT"))],
)
def match_candidates_for_search(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail="Search not found")
    require_client_access(user, search.client_id, db)
    if search.manual_state not in {"abierta", "activa", None} and classify_search(search, db) not in {"abierta", "activa"}:
        raise HTTPException(status_code=400, detail="Matching only available for active/open searches")

    org_id = db.get(Client, search.client_id).organization_id if db.get(Client, search.client_id) else None
    candidate_query = db.query(Candidate).filter(Candidate.archived_at.is_(None))
    if org_id is not None:
        org_clients = [c.id for c in db.query(Client.id).filter(Client.organization_id == org_id).all()]
        candidate_query = candidate_query.filter(
            (Candidate.client_id.in_(org_clients)) | (Candidate.search_id.isnot(None))
        )
    busy_ids = [
        row.candidate_id
        for row in db.query(CandidateSearchAssignment.candidate_id)
        .join(Search, Search.id == CandidateSearchAssignment.search_id)
        .filter(
            CandidateSearchAssignment.archived_at.is_(None),
            CandidateSearchAssignment.status.in_(PROJECT_STATUSES),
            Search.archived_at.is_(None),
        )
        .all()
    ]
    if busy_ids:
        candidate_query = candidate_query.filter(Candidate.id.notin_(busy_ids))
    candidates = candidate_query.order_by(Candidate.id.desc()).limit(250).all()

    client_context = build_client_context(db, search.client_id)
    payload_candidates = []
    for candidate in candidates:
        cv_text = ""
        if candidate.cv_file_url and candidate.cv_file_url.startswith("/uploads/"):
            full_path = Path(__file__).resolve().parents[2] / candidate.cv_file_url.lstrip("/")
            if full_path.exists():
                raw = full_path.read_bytes()
                if (candidate.cv_file_name or "").lower().endswith(".docx"):
                    cv_text = extract_docx_text(raw)
                else:
                    cv_text = extract_pdf_text(raw)
        payload_candidates.append(
            {
                "candidate_id": candidate.id,
                "name": candidate.full_name,
                "profile": candidate.short_profile,
                "cv_excerpt": cv_text[:2500],
            }
        )

    llm = matching_agent(
        search_title=search.title,
        job_description=search.job_description,
        client_context=client_context,
        candidates=payload_candidates,
    ) or {}
    rankings = llm.get("rankings") or []
    items: list[dict] = []
    ranking_map = {int(r.get("candidate_id")): r for r in rankings if r.get("candidate_id") is not None}
    for candidate in candidates:
        rank = ranking_map.get(candidate.id)
        if not rank:
            continue
        row = upsert_search_candidate_analysis(db, search=search, candidate=candidate, created_by=user.id, persist_note=False)
        row.match_score = float(rank.get("score") or 0)
        row.summary = str(rank.get("justification") or row.summary or "")
        row.recommendation_level = "alto" if row.match_score >= 7 else ("medio" if row.match_score >= 5 else "bajo")
        db.add(row)
        db.commit()
        db.refresh(row)
        if row.match_score >= 7:
            items.append(serialize_analysis(row, candidate.full_name))
    items.sort(key=lambda item: float(item.get("match_score") or 0), reverse=True)
    return {"search_id": search.id, "items": items}


@router.get(
    "/searches/{search_id}/ai/candidate-analyses",
    response_model=SearchCandidateAnalysesOut,
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def list_candidate_analyses_for_search(search_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = db.get(Search, search_id)
    if not search or search.archived_at is not None:
        raise HTTPException(status_code=404, detail="Search not found")
    require_client_access(user, search.client_id, db)
    rows = (
        db.query(SearchCandidateAnalysis, Candidate.full_name)
        .join(Candidate, Candidate.id == SearchCandidateAnalysis.candidate_id)
        .filter(SearchCandidateAnalysis.search_id == search_id)
        .order_by(SearchCandidateAnalysis.match_score.desc().nullslast(), SearchCandidateAnalysis.id.desc())
        .all()
    )
    return {
        "search_id": search_id,
        "items": [serialize_analysis(row, candidate_name) for row, candidate_name in rows],
    }


@router.get(
    "/candidates/{candidate_id}/search-analyses",
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def list_candidate_search_analyses(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    rows = (
        db.query(SearchCandidateAnalysis, Search.title)
        .join(Search, Search.id == SearchCandidateAnalysis.search_id)
        .filter(SearchCandidateAnalysis.candidate_id == candidate_id)
        .order_by(SearchCandidateAnalysis.match_score.desc().nullslast(), SearchCandidateAnalysis.id.desc())
        .all()
    )
    visible = []
    for row, search_title in rows:
        search = db.get(Search, row.search_id)
        if search and can_access_client(user, search.client_id, db):
            item = serialize_analysis(row, candidate.full_name)
            item["search_title"] = search_title
            visible.append(item)
    return {"candidate_id": candidate_id, "items": visible}


@router.post(
    "/mail/draft",
    response_model=MailDraftOut,
    dependencies=[Depends(require_roles("COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def create_mail_draft(payload: MailDraftRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, payload.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    search = db.get(Search, payload.search_id) if payload.search_id else None
    if search:
        require_client_access(user, search.client_id, db)

    interested_url = None
    not_interested_url = None
    if payload.kind == "contact":
        interested_url = _reply_url("preview", "interested")
        not_interested_url = _reply_url("preview", "not_interested")
    draft = generate_mail_draft(
        kind=payload.kind,
        candidate_name=candidate.full_name,
        search_title=search.title if search else None,
        search_description=search.job_description if search else None,
        extra_context=payload.extra_context,
        reason=payload.reason,
        interested_url=interested_url,
        not_interested_url=not_interested_url,
    )
    return {"subject": draft["subject"], "body": draft["body"], "kind": payload.kind}


@router.post(
    "/mail/send",
    response_model=CandidateOutreachOut,
    dependencies=[Depends(require_roles("COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def send_candidate_mail(payload: MailSendRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, payload.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    search = db.get(Search, payload.search_id) if payload.search_id else None
    if search:
        require_client_access(user, search.client_id, db)
    if not candidate.email:
        raise HTTPException(status_code=400, detail="Candidate email missing")

    outreach = CandidateOutreach(
        candidate_id=candidate.id,
        search_id=search.id if search else None,
        kind=payload.kind,
        subject=payload.subject,
        body=payload.body,
        status="draft",
        sent_by_user_id=user.id,
    )
    db.add(outreach)
    db.commit()
    db.refresh(outreach)

    body = payload.body
    if payload.kind == "contact":
        interested_token = CandidateOutreachToken(
            outreach_id=outreach.id,
            candidate_id=candidate.id,
            search_id=search.id if search else None,
            token=secrets.token_urlsafe(24),
            action_type="interested",
            expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        not_interested_token = CandidateOutreachToken(
            outreach_id=outreach.id,
            candidate_id=candidate.id,
            search_id=search.id if search else None,
            token=secrets.token_urlsafe(24),
            action_type="not_interested",
            expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        db.add(interested_token)
        db.add(not_interested_token)
        db.commit()
        body = (
            f"{body}\n\n"
            f"Estoy interesado: {_reply_url(interested_token.token, 'interested')}\n"
            f"No estoy interesado: {_reply_url(not_interested_token.token, 'not_interested')}"
        )

    result = send_mail_acting_as_user(db, user.id, candidate.email, payload.subject, body)
    outreach.body = body
    outreach.status = "sent" if result.get("status") == "sent" else result.get("status", "error")
    outreach.sent_at = datetime.now(timezone.utc) if outreach.status == "sent" else None
    db.add(outreach)
    db.commit()
    db.refresh(outreach)
    log_activity(
        db,
        entity_type="candidate",
        entity_id=candidate.id,
        action=f"mail_{payload.kind}_{outreach.status}",
        actor_user_id=user.id,
        summary=f"Mail {payload.kind} {outreach.status} para {candidate.full_name}",
        payload_json={"search_id": search.id if search else None, "outreach_id": outreach.id},
    )
    if outreach.status != "sent":
        mail_result_or_raise(result)
    outreach_payload = _serialize_outreach(outreach)
    outreach_payload["mail_sent_via"] = result.get("via")
    outreach_payload["mail_delivery_detail"] = result.get("message")
    return outreach_payload


@router.post("/outreach/reply/{token}", response_model=CandidateReplyOut)
def resolve_outreach_reply(
    token: str,
    action: str = Query(...),
    payload: InterviewProposalChoiceRequest | None = None,
    db: Session = Depends(get_db),
):
    row = db.query(CandidateOutreachToken).filter(CandidateOutreachToken.token == token).first()
    if not row:
        raise HTTPException(status_code=404, detail="Invalid token")
    if row.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used")
    if row.expires_at and row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    candidate = db.get(Candidate, row.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    search = db.get(Search, row.search_id) if row.search_id else None

    next_status = None
    if action == "interested":
        candidate.status = "pendiente_entrevista"
        if search and candidate.search_id is None:
            candidate.search_id = search.id
        next_status = candidate.status
        if search:
            create_event_notifications_for_roles(
                db,
                client_id=search.client_id,
                roles=["TALENT"],
                event_type="candidate_interested",
                title="Candidato interesado",
                message=f"{candidate.full_name} indicó interés en {search.title}.",
                metadata={"candidate_id": candidate.id, "search_id": search.id, "candidate_name": candidate.full_name},
            )
    elif action == "not_interested":
        candidate.search_id = None
        candidate.status = "banco_no_activo"
        next_status = candidate.status
    elif action in {"proposal_accept", "proposal_decline"}:
        event = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.candidate_id == candidate.id, CalendarEvent.search_id == row.search_id)
            .order_by(CalendarEvent.id.desc())
            .first()
        )
        if not event:
            raise HTTPException(status_code=404, detail="Calendar event not found")
        event.status = "confirmed" if action == "proposal_accept" else "rejected"
        if action == "proposal_accept":
            next_status = "pendiente_entrevista"
            candidate.status = "pendiente_entrevista"
            organizer = db.query(GoogleCalendarConnection).filter(GoogleCalendarConnection.user_id == event.created_by).first()
            search = db.get(Search, event.search_id) if event.search_id else None
            if organizer and search:
                attendees = [email for email in [candidate.email, search.contact_email] if email]
                try:
                    created = create_calendar_event(
                        connection=organizer,
                        summary=event.title,
                        description=event.notes or "",
                        start_dt=event.start_datetime,
                        end_dt=event.end_datetime,
                        attendee_emails=attendees,
                    )
                    if created:
                        event.google_event_id = created.get("id")
                        event.organizer_email = organizer.google_email or organizer.user_id
                except Exception:
                    pass
        db.add(event)
    else:
        raise HTTPException(status_code=400, detail="Unsupported action")

    row.used_at = datetime.now(timezone.utc)
    row.used_payload_json = {"action": action}
    db.add(row)
    db.add(candidate)
    db.commit()
    return {
        "status": "ok",
        "candidate_id": candidate.id,
        "search_id": row.search_id,
        "next_status": next_status,
    }


@router.get("/outreach/reply/{token}")
def resolve_outreach_reply_browser(token: str, action: str = Query(...), db: Session = Depends(get_db)):
    result = resolve_outreach_reply(token=token, action=action, payload=None, db=db)
    message = "Tu respuesta fue registrada correctamente."
    if result.get("next_status") == "pendiente_entrevista":
      message = "Gracias. Quedaste marcado como pendiente de entrevista."
    if result.get("next_status") == "banco_no_activo":
      message = "Gracias por responder. Te dejamos en banca no activa."
    return HTMLResponse(f"""
    <html>
      <head><title>Atipia</title></head>
      <body style=\"font-family: Arial, sans-serif; padding: 40px;\">
        <h2>{message}</h2>
        <p>Ya podés cerrar esta ventana.</p>
      </body>
    </html>
    """)


@router.get(
    "/candidates/{candidate_id}/notes",
    response_model=list[CandidateNoteOut],
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def list_candidate_notes(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    search = _candidate_access_search(user, candidate, db)
    rows = db.query(CandidateNote).filter(CandidateNote.candidate_id == candidate_id).order_by(CandidateNote.created_at.desc()).all()
    return [serialize_note(db, row) for row in rows if can_user_view_note(db, row, user)]


@router.post(
    "/candidates/{candidate_id}/notes",
    response_model=CandidateNoteOut,
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def create_candidate_note(candidate_id: int, payload: CandidateNoteCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    search = _candidate_access_search(user, candidate, db)
    note = CandidateNote(candidate_id=candidate_id, author_user_id=user.id, body=payload.body.strip())
    db.add(note)
    db.commit()
    db.refresh(note)
    replace_note_visibility(db, note.id, roles=payload.visible_roles, user_ids=payload.visible_user_ids)
    db.commit()
    if search:
        for role in payload.visible_roles:
            create_event_notifications_for_roles(
                db,
                client_id=search.client_id,
                roles=[role],
                event_type="candidate_note_created",
                title="Nueva nota en candidato",
                message=f"{user.full_name or user.email} agregó una nota en {candidate.full_name}.",
                metadata={"candidate_id": candidate.id, "note_id": note.id},
            )
        create_event_notifications_for_user_ids(
            db,
            user_ids=payload.visible_user_ids,
            event_type="candidate_note_created",
            title="Nueva nota en candidato",
            message=f"{user.full_name or user.email} agregó una nota en {candidate.full_name}.",
            metadata={"candidate_id": candidate.id, "note_id": note.id},
        )
    log_activity(
        db,
        entity_type="candidate",
        entity_id=candidate.id,
        action="note_created",
        actor_user_id=user.id,
        summary=f"Nota creada en {candidate.full_name}",
        payload_json={"note_id": note.id},
    )
    return serialize_note(db, note)


@router.patch(
    "/candidates/{candidate_id}/notes/{note_id}",
    response_model=CandidateNoteOut,
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def update_candidate_note(candidate_id: int, note_id: int, payload: CandidateNoteUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.get(CandidateNote, note_id)
    if not note or note.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="Note not found")
    if user.role != "SUPERADMIN" and user.id != note.author_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.body is not None:
        note.body = payload.body.strip()
    touch_note(note)
    db.add(note)
    db.commit()
    if payload.visible_roles is not None or payload.visible_user_ids is not None:
        replace_note_visibility(
            db,
            note.id,
            roles=payload.visible_roles if payload.visible_roles is not None else serialize_note(db, note)["visible_roles"],
            user_ids=payload.visible_user_ids if payload.visible_user_ids is not None else serialize_note(db, note)["visible_user_ids"],
        )
        db.commit()
    return serialize_note(db, note)


@router.delete(
    "/candidates/{candidate_id}/notes/{note_id}",
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def delete_candidate_note(candidate_id: int, note_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.get(CandidateNote, note_id)
    if not note or note.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="Note not found")
    if user.role != "SUPERADMIN" and user.id != note.author_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    db.query(CandidateNote).filter(CandidateNote.id == note_id).delete()
    db.commit()
    return {"status": "ok"}


@router.get(
    "/google-calendar/status",
    response_model=GoogleCalendarStatusOut,
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def google_calendar_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(GoogleCalendarConnection).filter(GoogleCalendarConnection.user_id == user.id).first()
    return {
        "connected": bool(row and row.access_token),
        "google_email": row.google_email if row else None,
        "expires_at": row.expires_at.isoformat() if row and row.expires_at else None,
        "gmail_send_enabled": google_connection_can_send_mail(row),
        "oauth_configured": google_oauth_env_configured(),
        "can_send_mail": user_can_send_mail(db, user.id),
    }


_OAUTH_USER_ERROR = (
    "La conexión con Google no está disponible en este momento. "
    "Contactá al administrador de la plataforma."
)


def _google_oauth_popup_html(*, ok: bool, message: str = "") -> HTMLResponse:
    status = "success" if ok else "error"
    title = "Conexión correcta" if ok else "No se pudo conectar"
    body = (
        "Volvé a la aplicación; esta ventana se cerrará sola."
        if ok
        else (message or "Intentá de nuevo desde Perfil.")
    )
    safe_message = json.dumps(message or "")
    close_ms = 400 if ok else 1200
    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"><title>{title}</title></head>
    <body style="font-family:sans-serif;padding:48px;text-align:center;">
      <p style="font-size:18px;margin:0 0 12px;">{title}.</p>
      <p style="color:#555;margin:0;font-size:15px;">{body}</p>
      <script>
        (function () {{
          var payload = {{ type: "atipia-google-oauth", status: "{status}", message: {safe_message} }};
          if (window.opener && !window.opener.closed) {{
            try {{ window.opener.postMessage(payload, "*"); }} catch (e) {{}}
          }}
          setTimeout(function () {{ window.close(); }}, {close_ms});
        }})();
      </script>
    </body></html>
    """)


@router.get(
    "/google-calendar/connect",
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def google_calendar_connect(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not google_oauth_env_configured():
        raise HTTPException(status_code=400, detail=_OAUTH_USER_ERROR)
    row = db.query(GoogleCalendarConnection).filter(GoogleCalendarConnection.user_id == user.id).first()
    force_consent = not (row and row.refresh_token)
    state = f"user:{user.id}:{secrets.token_urlsafe(12)}"
    return {"url": build_google_oauth_url(state=state, force_consent=force_consent)}


@router.get("/google-calendar/callback")
def google_calendar_callback(
    state: str = Query(...),
    code: str | None = Query(None),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if error:
        msg = "Cancelaste la conexión con Google." if error == "access_denied" else "Google no autorizó la conexión."
        return _google_oauth_popup_html(ok=False, message=msg)
    if not code:
        return _google_oauth_popup_html(ok=False, message="Faltó el código de autorización. Intentá de nuevo.")
    if not google_oauth_env_configured():
        return _google_oauth_popup_html(ok=False, message=_OAUTH_USER_ERROR)
    settings = get_settings()
    try:
        _, user_id, _ = state.split(":", 2)
        user = db.get(User, int(user_id))
    except Exception:
        return _google_oauth_popup_html(ok=False, message="La sesión expiró. Volvé a la app e intentá de nuevo.")
    if not user:
        return _google_oauth_popup_html(ok=False, message="Usuario no encontrado.")

    import requests

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if not token_response.ok:
        return _google_oauth_popup_html(ok=False, message="No se pudo completar el inicio de sesión con Google.")
    payload = token_response.json()
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = int(payload.get("expires_in") or 3600)

    profile_response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    profile = profile_response.json() if profile_response.ok else {}
    row = db.query(GoogleCalendarConnection).filter(GoogleCalendarConnection.user_id == user.id).first()
    if not row:
        row = GoogleCalendarConnection(user_id=user.id)
    row.google_email = profile.get("email")
    row.access_token = access_token
    row.refresh_token = refresh_token or row.refresh_token
    row.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    row.scope = payload.get("scope") or oauth_scope_string()
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return _google_oauth_popup_html(ok=True)


@router.post(
    "/google-calendar/disconnect",
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def google_calendar_disconnect(user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(GoogleCalendarConnection).filter(GoogleCalendarConnection.user_id == user.id).first()
    if row:
        db.delete(row)
        db.commit()
    return {"status": "ok"}


@router.post(
    "/interviews/proposals",
    dependencies=[Depends(require_roles("TALENT", "SUPERADMIN"))],
)
def create_interview_proposal(payload: InterviewProposalRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, payload.candidate_id)
    search = db.get(Search, payload.search_id)
    if not candidate or not search:
        raise HTTPException(status_code=404, detail="Candidate or search not found")
    require_client_access(user, search.client_id, db)
    if not candidate.email:
        raise HTTPException(status_code=400, detail="Candidate email missing")
    if not payload.slot_options:
        raise HTTPException(status_code=400, detail="At least one slot option is required")

    first = payload.slot_options[0]
    event = CalendarEvent(
        title=payload.title,
        start_datetime=datetime.fromisoformat(first["start_datetime"]),
        end_datetime=datetime.fromisoformat(first["end_datetime"]),
        kind="interview_proposal",
        status="pending",
        notes=payload.notes,
        meeting_url=payload.meeting_url,
        invite_emails_json=[candidate.email],
        client_id=search.client_id,
        search_id=search.id,
        candidate_id=candidate.id,
        created_by=user.id,
        organizer_email=user.email,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    outreach = CandidateOutreach(
        candidate_id=candidate.id,
        search_id=search.id,
        kind="interview_invite",
        subject=f"Propuesta de entrevista - {search.title}",
        body="",
        status="draft",
        sent_by_user_id=user.id,
    )
    db.add(outreach)
    db.commit()
    db.refresh(outreach)

    accept_token = CandidateOutreachToken(
        outreach_id=outreach.id,
        candidate_id=candidate.id,
        search_id=search.id,
        token=secrets.token_urlsafe(24),
        action_type="proposal_accept",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    decline_token = CandidateOutreachToken(
        outreach_id=outreach.id,
        candidate_id=candidate.id,
        search_id=search.id,
        token=secrets.token_urlsafe(24),
        action_type="proposal_decline",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(accept_token)
    db.add(decline_token)
    db.commit()

    slot_lines = "\n".join(
        f"- {item.get('start_datetime')} a {item.get('end_datetime')}" for item in payload.slot_options
    )
    footer = (
        "Opciones propuestas:\n"
        f"{slot_lines}\n\n"
        f"Aceptar propuesta: {_reply_url(accept_token.token, 'proposal_accept')}\n"
        f"Rechazar propuesta: {_reply_url(decline_token.token, 'proposal_decline')}\n"
    )
    if payload.email_body_override and str(payload.email_body_override).strip():
        body = str(payload.email_body_override).strip().rstrip() + "\n\n" + footer
    else:
        intro = (
            f"Hola {candidate.full_name},\n\n"
            f"Queremos coordinar una entrevista para {search.title}.\n"
        )
        extra = []
        if payload.notes and str(payload.notes).strip():
            extra.append(str(payload.notes).strip())
        if payload.meeting_url and str(payload.meeting_url).strip():
            extra.append(f"Link de reunión: {payload.meeting_url.strip()}")
        notes_block = ("\n\n" + "\n".join(extra) + "\n\n") if extra else "\n"
        body = intro + notes_block + footer
    result = send_mail_acting_as_user(db, user.id, candidate.email, outreach.subject, body)
    outreach.body = body
    outreach.status = "sent" if result.get("status") == "sent" else result.get("status", "error")
    outreach.sent_at = datetime.now(timezone.utc) if outreach.status == "sent" else None
    db.add(outreach)
    db.commit()
    if outreach.status != "sent":
        mail_result_or_raise(result)
    return {
        "status": "ok",
        "event_id": event.id,
        "outreach_id": outreach.id,
        "mail_sent_via": result.get("via"),
        "mail_delivery_detail": result.get("message"),
    }


@router.post(
    "/transcripts",
    response_model=TranscriptOut,
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def upsert_transcript(payload: TranscriptUpsertRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    interview = db.get(Interview, payload.interview_id)
    candidate = db.get(Candidate, payload.candidate_id)
    if not interview or not candidate or interview.candidate_id != candidate.id:
        raise HTTPException(status_code=404, detail="Interview or candidate not found")
    search = _candidate_access_search(user, candidate, db)
    row = (
        db.query(InterviewTranscript)
        .filter(InterviewTranscript.interview_id == interview.id, InterviewTranscript.source_type == payload.source_type)
        .first()
    )
    if not row:
        row = InterviewTranscript(
            interview_id=interview.id,
            candidate_id=candidate.id,
            source_type=payload.source_type,
            content=payload.content.strip(),
            created_by=user.id,
        )
    else:
        row.content = payload.content.strip()
        row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "interview_id": row.interview_id,
        "candidate_id": row.candidate_id,
        "source_type": row.source_type,
        "content": row.content,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post(
    "/transcripts/upload",
    response_model=TranscriptOut,
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
async def upload_transcript_file(
    interview_id: int = Form(...),
    candidate_id: int = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    content = raw.decode("utf-8", errors="ignore")
    if file.filename.lower().endswith(".docx"):
        html = mammoth.convert_to_html(BytesIO(raw)).value
        content = mammoth.extract_raw_text(BytesIO(raw)).value or html
    return upsert_transcript(
        TranscriptUpsertRequest(
            interview_id=interview_id,
            candidate_id=candidate_id,
            source_type="uploaded_file",
            content=content,
        ),
        user=user,
        db=db,
    )


@router.get(
    "/candidates/{candidate_id}/cv-html",
    response_model=CvHtmlOut,
    dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))],
)
def candidate_cv_html(candidate_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    search = _candidate_access_search(user, candidate, db)
    if not candidate.cv_file_url or not candidate.cv_file_url.startswith("/uploads/"):
        raise HTTPException(status_code=400, detail="Inline rendering only supported for local uploaded files")
    full_path = Path(__file__).resolve().parents[2] / candidate.cv_file_url.lstrip("/")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="CV file not found")
    raw = full_path.read_bytes()
    if (candidate.cv_file_name or "").lower().endswith(".docx"):
        html = mammoth.convert_to_html(BytesIO(raw)).value
        return {"candidate_id": candidate.id, "file_name": candidate.cv_file_name, "html": html, "source_type": "docx_html"}
    raise HTTPException(status_code=400, detail="HTML rendering is only available for DOCX")
