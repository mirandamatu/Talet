from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.candidate_note import CandidateNote
from app.models.candidate_note_visibility import CandidateNoteVisibility
from app.models.user import User


def can_user_view_note(db: Session, note: CandidateNote, user: User) -> bool:
    if user.role == "SUPERADMIN" or user.id == note.author_user_id:
        return True
    rows = db.query(CandidateNoteVisibility).filter(CandidateNoteVisibility.note_id == note.id).all()
    visible_roles = {row.role for row in rows if row.role}
    visible_users = {row.user_id for row in rows if row.user_id is not None}
    return user.role in visible_roles or user.id in visible_users


def replace_note_visibility(db: Session, note_id: int, *, roles: list[str], user_ids: list[int]) -> None:
    db.query(CandidateNoteVisibility).filter(CandidateNoteVisibility.note_id == note_id).delete()
    for role in sorted(set(roles or [])):
        db.add(CandidateNoteVisibility(note_id=note_id, role=role))
    for user_id in sorted(set(user_ids or [])):
        db.add(CandidateNoteVisibility(note_id=note_id, user_id=user_id))


def serialize_note(db: Session, note: CandidateNote) -> dict:
    rows = db.query(CandidateNoteVisibility).filter(CandidateNoteVisibility.note_id == note.id).all()
    author = db.get(User, note.author_user_id)
    return {
        "id": note.id,
        "candidate_id": note.candidate_id,
        "author_user_id": note.author_user_id,
        "author_name": author.full_name if author else None,
        "body": note.body,
        "note_type": note.note_type,
        "is_pinned": note.is_pinned,
        "search_id": note.search_id,
        "visible_roles": [row.role for row in rows if row.role],
        "visible_user_ids": [row.user_id for row in rows if row.user_id is not None],
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def touch_note(note: CandidateNote) -> None:
    note.updated_at = datetime.now(timezone.utc)
