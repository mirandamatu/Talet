from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.candidate_presentation import CandidatePresentation
from app.models.user import User


def get_presentation(db: Session, candidate_id: int, search_id: int | None = None) -> CandidatePresentation | None:
    query = db.query(CandidatePresentation).filter(CandidatePresentation.candidate_id == candidate_id)
    if search_id is not None:
        query = query.filter(CandidatePresentation.search_id == search_id)
    return query.order_by(CandidatePresentation.presented_at.desc()).first()


def is_presented_to_client(db: Session, candidate_id: int, search_id: int | None = None) -> bool:
    return get_presentation(db, candidate_id, search_id) is not None


def present_candidate(
    db: Session,
    *,
    candidate_id: int,
    search_id: int,
    presented_by: int,
    notes: str | None = None,
) -> CandidatePresentation:
    existing = (
        db.query(CandidatePresentation)
        .filter(
            CandidatePresentation.candidate_id == candidate_id,
            CandidatePresentation.search_id == search_id,
        )
        .first()
    )
    if existing:
        return existing
    row = CandidatePresentation(
        candidate_id=candidate_id,
        search_id=search_id,
        presented_by=presented_by,
        presented_at=datetime.now(timezone.utc),
        notes=(notes or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_assigned_talent(db: Session, search) -> User | None:
    if search.assigned_talent_user_id:
        user = db.get(User, search.assigned_talent_user_id)
        if user and user.is_active:
            return user
    return None
