from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.candidate_note import CandidateNote
from app.services.candidate_notes import replace_note_visibility, serialize_note


def create_pinned_ai_note(
    db: Session,
    *,
    candidate_id: int,
    search_id: int,
    author_user_id: int | None,
    note_type: str,
    body: str,
    visible_roles: list[str] | None = None,
) -> CandidateNote:
    db.query(CandidateNote).filter(
        CandidateNote.candidate_id == candidate_id,
        CandidateNote.search_id == search_id,
        CandidateNote.note_type == note_type,
        CandidateNote.is_pinned.is_(True),
    ).update({"is_pinned": False})
    note = CandidateNote(
        candidate_id=candidate_id,
        search_id=search_id,
        author_user_id=author_user_id or 1,
        note_type=note_type,
        is_pinned=True,
        body=body,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    replace_note_visibility(db, note.id, roles=visible_roles or ["TALENT", "COMERCIAL", "SUPERADMIN"], user_ids=[])
    db.commit()
    return note


def list_pinned_notes(db: Session, candidate_id: int, search_id: int | None = None) -> list[dict]:
    query = db.query(CandidateNote).filter(CandidateNote.candidate_id == candidate_id, CandidateNote.is_pinned.is_(True))
    if search_id is not None:
        query = query.filter(CandidateNote.search_id == search_id)
    rows = query.order_by(CandidateNote.created_at.desc()).all()
    return [serialize_note(db, row) for row in rows]
