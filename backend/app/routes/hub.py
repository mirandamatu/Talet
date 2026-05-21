from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.models.hub import Conversation, ConversationParticipant, ConversationSummary, Message
from app.models.user import User
from app.services.ai_agents import conversation_summary_agent
from app.services.notifications import notify_users
from app.services.tenancy import require_organization_id
from app.services.user_clients import can_access_client, get_user_client_ids

router = APIRouter(prefix="/hub", tags=["hub"])

ALLOWED_TYPES = {"recruiter_client", "recruiter_recruiter", "internal_group", "client_group"}


class ConversationCreate(BaseModel):
    conversation_type: str
    title: str
    client_id: int | None = None
    participant_user_ids: list[int] = []


class MessageCreate(BaseModel):
    body: str


def _can_access_conversation(db: Session, user: User, conversation: Conversation) -> bool:
    if user.role == "SUPERADMIN" and conversation.organization_id == user.organization_id:
        return True
    participant = (
        db.query(ConversationParticipant)
        .filter(ConversationParticipant.conversation_id == conversation.id, ConversationParticipant.user_id == user.id)
        .first()
    )
    if participant:
        return True
    if conversation.conversation_type in {"internal_group"} and user.role == "CLIENTE":
        return False
    if conversation.client_id and user.role != "CLIENTE":
        return can_access_client(user, conversation.client_id, db)
    return False


def _validate_participants(db: Session, user: User, conversation_type: str, client_id: int | None, participant_ids: list[int]) -> list[User]:
    users = db.query(User).filter(User.id.in_(sorted(set(participant_ids + [user.id]))), User.is_active.is_(True)).all()
    if conversation_type in {"recruiter_client", "client_group"}:
        if client_id is None:
            raise HTTPException(status_code=400, detail="client_id required")
        client_user_ids = set(get_user_client_ids(db.query(User).filter(User.client_id == client_id).first() or user))
        for participant in users:
            if participant.role == "CLIENTE" and participant.client_id != client_id and participant.client_id not in client_user_ids:
                raise HTTPException(status_code=400, detail="Cannot mix client contacts from other clients")
    if conversation_type == "internal_group":
        if any(u.role == "CLIENTE" for u in users):
            raise HTTPException(status_code=400, detail="Internal groups cannot include clients")
    return users


@router.get("/conversations", dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))])
def list_conversations(user=Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = require_organization_id(user)
    rows = db.query(Conversation).filter(Conversation.organization_id == org_id).order_by(Conversation.updated_at.desc().nullslast(), Conversation.id.desc()).all()
    visible = [row for row in rows if _can_access_conversation(db, user, row)]
    return [
        {
            "id": row.id,
            "title": row.title,
            "conversation_type": row.conversation_type,
            "client_id": row.client_id,
            "updated_at": row.updated_at.isoformat() if row.updated_at else row.created_at.isoformat(),
        }
        for row in visible
    ]


@router.post("/conversations", dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))])
def create_conversation(payload: ConversationCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = require_organization_id(user)
    if payload.conversation_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid conversation type")
    if payload.client_id and not can_access_client(user, payload.client_id, db):
        raise HTTPException(status_code=403, detail="Forbidden")
    participants = _validate_participants(db, user, payload.conversation_type, payload.client_id, payload.participant_user_ids)
    row = Conversation(
        organization_id=org_id,
        client_id=payload.client_id,
        conversation_type=payload.conversation_type,
        title=payload.title.strip(),
        created_by=user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    for participant in participants:
        db.add(ConversationParticipant(conversation_id=row.id, user_id=participant.id))
    db.commit()
    return {"id": row.id, "title": row.title}


@router.get("/conversations/{conversation_id}/messages", dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))])
def list_messages(conversation_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or not _can_access_conversation(db, user, conversation):
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id).limit(200).all()
    return [
        {
            "id": row.id,
            "sender_id": row.sender_id,
            "body": row.body,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/conversations/{conversation_id}/messages", dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))])
def send_message(conversation_id: int, payload: MessageCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or not _can_access_conversation(db, user, conversation):
        raise HTTPException(status_code=404, detail="Conversation not found")
    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message body required")
    row = Message(conversation_id=conversation_id, sender_id=user.id, body=body)
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.add(conversation)
    db.commit()
    db.refresh(row)
    participants = (
        db.query(User)
        .join(ConversationParticipant, ConversationParticipant.user_id == User.id)
        .filter(ConversationParticipant.conversation_id == conversation_id, User.id != user.id, User.is_active.is_(True))
        .all()
    )
    notify_users(
        db,
        participants,
        event_type="hub_message_received",
        title="Nuevo mensaje en el hub",
        message=f'Nuevo mensaje en "{conversation.title}"',
        metadata={"conversation_id": conversation_id},
        client_id=conversation.client_id,
    )
    return {"id": row.id, "status": "ok"}


@router.post("/conversations/{conversation_id}/summarize", dependencies=[Depends(require_roles("COMERCIAL", "TALENT", "SUPERADMIN"))])
def summarize_conversation(conversation_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or not _can_access_conversation(db, user, conversation):
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.id).all()
    if not rows:
        raise HTTPException(status_code=400, detail="No messages to summarize")
    transcript = "\n".join(f"Usuario {m.sender_id}: {m.body}" for m in rows)
    llm = conversation_summary_agent(messages_text=transcript) or {}
    summary = ConversationSummary(
        conversation_id=conversation_id,
        summary=str(llm.get("summary") or "Sin resumen disponible."),
        action_items_json=[str(item) for item in (llm.get("action_items") or [])[:20]],
        created_by=user.id,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return {
        "id": summary.id,
        "summary": summary.summary,
        "action_items": summary.action_items_json or [],
    }


@router.get("/conversations/{conversation_id}/summaries", dependencies=[Depends(require_roles("CLIENTE", "COMERCIAL", "TALENT", "SUPERADMIN"))])
def list_summaries(conversation_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or not _can_access_conversation(db, user, conversation):
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = db.query(ConversationSummary).filter(ConversationSummary.conversation_id == conversation_id).order_by(ConversationSummary.id.desc()).all()
    return [
        {
            "id": row.id,
            "summary": row.summary,
            "action_items": row.action_items_json or [],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
